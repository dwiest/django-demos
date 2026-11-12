"""Inventory MCP adapter. Python 3.12 / x86_64 / API Gateway HTTP API payload v2."""
import asyncio
import base64
import json
import logging
import hmac
import os
import re
import time
from typing import Annotated, Any, Literal
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, build_opener, HTTPRedirectHandler

import cognito_auth
import anyio
from mangum import Mangum
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field, field_validator

PATH = os.environ.get("MCP_PATH", "/api/inventory-mcp")
MAX_BODY_SIZE = 1024 * 1024
API_TIMEOUT_SECONDS = 20
logging.getLogger("mcp").setLevel(logging.WARNING)
logging.getLogger("mangum").setLevel(logging.WARNING)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class DjangoAPIError(Exception):
    def __init__(self, status: int, code: str):
        self.status = status
        self.code = code
        super().__init__(code)


def http_response(status, body, headers=None):
    return {"statusCode": status, "headers": {
        "Content-Type": "application/json", "Cache-Control": "no-store",
        **(headers or {}),
    }, "body": json.dumps(body), "isBase64Encoded": False}


def django_request(method: str, relative_path: str, *, query=None, payload=None):
    """Call the configured Django REST API without exposing response internals in logs."""
    base = os.environ.get("DJANGO_API_BASE_URL", "").strip().rstrip("/")
    if not base.startswith("https://"):
        raise ValueError("DJANGO_API_BASE_URL must be configured with an HTTPS URL")
    url = base + "/" + relative_path.lstrip("/")
    if query:
        url += "?" + urlencode(query)
    headers = {"Accept": "application/json"}
    authorization = os.environ.get("DJANGO_API_AUTHORIZATION", "").strip()
    if authorization:
        headers["Authorization"] = authorization
    else:
        raise ValueError("DJANGO_API_AUTHORIZATION is required")
    body = None
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = Request(url, data=body, headers=headers, method=method)
    try:
        with build_opener(NoRedirect()).open(req, timeout=API_TIMEOUT_SECONDS) as response:
            response_body = response.read(MAX_BODY_SIZE + 1)
            status = response.status
    except HTTPError as exc:
        try:
            error_data = json.loads(exc.read(8192).decode("utf-8", "replace"))
            code = error_data.get("error") or error_data.get("detail") or "django_api_error"
            if not isinstance(code, str):
                code = "django_api_error"
            code = re.sub(r"[^A-Za-z0-9_. -]", "", code)[:160] or "django_api_error"
        except Exception:
            code = "django_api_error"
        raise DjangoAPIError(exc.code, code) from None
    except (URLError, TimeoutError, OSError):
        raise DjangoAPIError(502, "django_api_unavailable") from None
    if not 200 <= status < 300:
        raise DjangoAPIError(status, "django_api_error")
    if len(response_body) > MAX_BODY_SIZE:
        raise DjangoAPIError(502, "django_api_response_too_large")
    if status == 204:
        return {"success": True}
    try:
        return json.loads(response_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise DjangoAPIError(502, "django_api_invalid_json") from None


# This adapter runs separately from the Python 3.7 Django installation.
ID = Annotated[int, Field(strict=True, ge=1)]
Quantity = Annotated[int, Field(strict=True, ge=0, le=2147483647)]
Page = Annotated[int, Field(ge=1)]
PageSize = Annotated[int, Field(ge=1, le=100)]
Key = Annotated[str, Field(min_length=1, max_length=128)]


class CatalogChanges(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(default=None, min_length=1, max_length=255)
    description: str = Field(default=None, min_length=1, max_length=255)
    status: Literal[-1, 0, 1] = None


def make_server(event):
    hosts = {os.environ.get("PUBLIC_HOST", "wiest.world")}
    gateway_host = event.get("requestContext", {}).get("domainName")
    if gateway_host:
        hosts.add(gateway_host)
    mcp = FastMCP(
        "Wiest Inventory",
        instructions=(
            "Manage the authenticated Django user's inventory via REST. Items are catalog "
            "records; stock quantities belong to entries within inventory lists. Search "
            "before creating: creation requests are NOT idempotent and must not be blindly "
            "retried after timeouts. Only apply changes requested or approved by the user. "
            "Grocery arrivals add stock; pantry photos are partial observations, not proof "
            "that unseen items are absent. Do not set quantities from photos without review. "
            "Reuse the same idempotency_key AND identical arguments when retrying an "
            "adjustment; use a new key for a new action. Never generate a new key just "
            "because an adjustment timed out. Transaction results describe the original "
            "adjustment; get_inventory_entry returns the current quantity."
        ),
        stateless_http=True, json_response=True, streamable_http_path=PATH,
        max_request_body_size=MAX_BODY_SIZE,
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=True, allowed_hosts=sorted(hosts),
            allowed_origins=["https://" + host for host in sorted(hosts)]),
    )
    read = ToolAnnotations(readOnlyHint=True, destructiveHint=False,
                           idempotentHint=True, openWorldHint=False)
    create = ToolAnnotations(readOnlyHint=False, destructiveHint=False,
                             idempotentHint=False, openWorldHint=False)
    write = ToolAnnotations(readOnlyHint=False, destructiveHint=True,
                            idempotentHint=True, openWorldHint=False)

    async def call(method, path, query=None, payload=None):
        try:
            return await anyio.to_thread.run_sync(
                lambda: django_request(method, path, query=query, payload=payload))
        except DjangoAPIError as exc:
            raise ValueError(f"inventory_api_failed:{exc.status}:{exc.code}") from None

    @mcp.tool(annotations=read)
    async def search_inventory_items(term: str = "", page: Page = 1,
                                     page_size: PageSize = 40) -> dict[str, Any]:
        """Search item names (case-insensitive substring); empty term lists the catalog."""
        return await call("GET", "items/", dict(term=term, page=page, page_size=page_size))

    @mcp.tool(annotations=read)
    async def get_inventory_item(item_id: ID) -> dict[str, Any]:
        """Get a catalog item. Its stock is held in entries, not this record."""
        return await call("GET", f"items/{item_id}/")

    @mcp.tool(annotations=create)
    async def create_inventory_item(
        name: Annotated[str, Field(min_length=1, max_length=255)],
        description: Annotated[str, Field(min_length=1, max_length=255)], status: Literal[-1, 0, 1] = 0,
    ) -> dict[str, Any]:
        """Create a catalog item after searching for existing names. Not safe to blindly retry."""
        return await call("POST", "items/", payload=dict(name=name, description=description, status=status))

    @mcp.tool(annotations=write)
    async def update_inventory_item(item_id: ID, changes: CatalogChanges) -> dict[str, Any]:
        """Patch supplied catalog fields; cannot change stock quantities."""
        payload = changes.model_dump(exclude_unset=True)
        if not payload or any(v is None for v in payload.values()):
            raise ValueError("provide_non_null_changes")
        return await call("PATCH", f"items/{item_id}/", payload=payload)

    @mcp.tool(annotations=read)
    async def search_inventory_lists(term: str = "", page: Page = 1,
                                     page_size: PageSize = 40) -> dict[str, Any]:
        """Search inventory list names; empty term lists locations/collections."""
        return await call("GET", "lists/", dict(term=term, page=page, page_size=page_size))

    @mcp.tool(annotations=read)
    async def get_inventory_list(list_id: ID) -> dict[str, Any]:
        """Get an inventory list by ID."""
        return await call("GET", f"lists/{list_id}/")

    @mcp.tool(annotations=create)
    async def create_inventory_list(
        name: Annotated[str, Field(min_length=1, max_length=255)],
        description: Annotated[str, Field(min_length=1, max_length=255)], status: Literal[-1, 0, 1] = 0,
    ) -> dict[str, Any]:
        """Create an inventory list after searching for an existing one. Not idempotent."""
        return await call("POST", "lists/", payload=dict(name=name, description=description, status=status))

    @mcp.tool(annotations=write)
    async def update_inventory_list(list_id: ID, changes: CatalogChanges) -> dict[str, Any]:
        """Patch supplied list fields; omitted fields remain unchanged."""
        payload = changes.model_dump(exclude_unset=True)
        if not payload or any(v is None for v in payload.values()):
            raise ValueError("provide_non_null_changes")
        return await call("PATCH", f"lists/{list_id}/", payload=payload)

    @mcp.tool(annotations=read)
    async def search_inventory_entries(
        term: str = "", item_id: ID | None = None, list_id: ID | None = None,
        page: Page = 1, page_size: PageSize = 40,
    ) -> dict[str, Any]:
        """Find stock entries by item name and/or item/list IDs. Returns paginated results."""
        query = dict(term=term, page=page, page_size=page_size)
        if item_id is not None:
            query['item'] = item_id
        if list_id is not None:
            query['inventory_list'] = list_id
        return await call("GET", "entries/", query)

    @mcp.tool(annotations=read)
    async def get_inventory_entry(entry_id: ID) -> dict[str, Any]:
        """Get an entry's current quantity and item/list IDs."""
        return await call("GET", f"entries/{entry_id}/")

    @mcp.tool(annotations=create)
    async def create_inventory_entry(
        item_id: ID, list_id: ID, quantity: Quantity = 1,
        status: Literal[-1, 0, 1] = 0,
    ) -> dict[str, Any]:
        """Create stock and initial ledger event. Search entries first: duplicates are allowed.

        Not idempotent. After an uncertain response, reconcile with entries/history
        instead of resubmitting this creation automatically.
        """
        return await call("POST", "entries/", payload=dict(
            item=item_id, inventory_list=list_id, quantity=quantity, status=status))

    @mcp.tool(annotations=write)
    async def adjust_inventory_quantity(
        entry_id: ID, operation: Literal['add', 'remove', 'set'], quantity: Quantity,
        idempotency_key: Key, reference_id: Annotated[str, Field(max_length=128)] = "",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Atomically add/remove/set an entry's quantity and record its transaction.

        Supply a stable key for this action. Retry with the SAME key and arguments;
        do not create a fresh key on timeout. Remove cannot produce negative stock.
        Set replaces the balance and needs explicit user intent. Returns the ledger
        event, including before/after; an identical retry returns the original event.
        """
        if not idempotency_key.strip():
            raise ValueError("idempotency_key_must_not_be_blank")
        return await call("POST", f"entries/{entry_id}/adjust/", payload=dict(
            operation=operation, quantity=quantity, idempotency_key=idempotency_key,
            source='mcp', reference_id=reference_id, metadata=metadata or {}))

    @mcp.tool(annotations=read)
    async def list_inventory_transactions(
        entry_id: ID | None = None, page: Page = 1, page_size: PageSize = 40,
    ) -> dict[str, Any]:
        """Read quantity history for one entry, or all history for the authenticated user."""
        path = f"entries/{entry_id}/transactions/" if entry_id is not None else "transactions/"
        return await call("GET", path, dict(page=page, page_size=page_size))

    return mcp


def make_app(event, context):
    return make_server(event).streamable_http_app()


def lambda_handler(event, context):
    headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
    method = event.get("requestContext", {}).get("http", {}).get("method", "")
    path = event.get("rawPath", "")
    mode = os.environ.get("AUTH_MODE", "static")
    if mode == "cognito":
        try:
            metadata = cognito_auth.discovery()
            auth_metadata = cognito_auth.authorization_metadata()
            if path == '/.well-known/oauth-authorization-server':
                if method != 'GET':
                    return http_response(405, {'error': 'method_not_allowed'}, {'Allow': 'GET'})
                return http_response(200, auth_metadata, {'Access-Control-Allow-Origin': '*'})
            if path in (cognito_auth.metadata_path(metadata['resource']),
                        '/.well-known/oauth-protected-resource'):
                if method != 'GET':
                    return http_response(405, {'error': 'method_not_allowed'}, {'Allow': 'GET'})
                return http_response(200, metadata, {'Access-Control-Allow-Origin': '*'})
            cognito_auth.verify(headers.get('authorization', ''))
        except cognito_auth.AuthError as exc:
            challenge = cognito_auth.challenge(exc.code) if exc.status in (401, 403) else {}
            return http_response(exc.status, {'error': exc.code}, challenge)
    elif mode == "static":
        token = os.environ.get("MCP_AUTH_TOKEN", "")
        if not token:
            return http_response(503, {"error": "mcp_auth_not_configured"})
        if not hmac.compare_digest(headers.get("authorization", ""), "Bearer " + token):
            return http_response(401, {"error": "unauthorized"}, {"WWW-Authenticate": "Bearer"})
    else:
        return http_response(503, {'error': 'invalid_auth_mode'})
    if path.rstrip("/") != PATH.rstrip("/"):
        return http_response(404, {"error": "route_not_found", "mcpPath": PATH})
    if method in ("GET", "DELETE"):
        return http_response(405, {"name": "Wiest Inventory", "transport": "streamable-http",
            "message": f"Connect using an MCP client. POST JSON-RPC to {PATH}."}, {"Allow": "POST"})
    if method != "POST":
        return http_response(405, {"error": "method_not_allowed"}, {"Allow": "POST"})
    try:
        body = event.get("body") or ""
        size = len(base64.b64decode(body, validate=True)) if event.get("isBase64Encoded") else len(body.encode())
        if size > MAX_BODY_SIZE:
            return http_response(413, {"error": "request_too_large"})
    except (ValueError, TypeError, AttributeError):
        return http_response(400, {"error": "invalid_body_encoding"})
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    started = time.monotonic()
    try:
        adapter = Mangum(make_app(event, context), lifespan="on")
        result = adapter(event, context)
        result.setdefault("headers", {})["cache-control"] = "no-store"
        return result
    except Exception as exc:
        print(json.dumps({"event": "mcp_internal_error", "type": type(exc).__name__,
            "requestId": getattr(context, "aws_request_id", None),
            "latencyMs": round((time.monotonic() - started) * 1000)}))
        return http_response(500, {"error": "mcp_internal_error"})
    finally:
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()
        asyncio.set_event_loop(None)

