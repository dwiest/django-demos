# Inventory MCP Lambda

Separate Python 3.12 / x86_64 Lambda adapter, following the Bookmarks MCP v3
pattern: FastMCP, stateless Streamable HTTP, JSON responses, Mangum, and API
Gateway HTTP API payload v2. Calls Inventory REST over HTTPS; it never imports
Django or accesses the database. No changes to the EC2 Python environment.

## Tools

| Tools | Purpose |
| --- | --- |
| `search_inventory_items`, `get_inventory_item` | Find catalog records |
| `create_inventory_item`, `update_inventory_item` | Create or patch catalog fields |
| `search_inventory_lists`, `get_inventory_list` | Find inventory collections/locations |
| `create_inventory_list`, `update_inventory_list` | Create or patch lists |
| `search_inventory_entries`, `get_inventory_entry` | Find stock and current quantities |
| `create_inventory_entry` | Create stock and initial transaction |
| `adjust_inventory_quantity` | Atomic add/remove/set with required retry key |
| `list_inventory_transactions` | Owner history, optionally for one entry |

Searches return the API's paginated `count`, `next`, `previous`, and `results`.
Use the page argument to continue; the server never follows arbitrary URLs.
All records belong to the Django account configured below. Item and list names
retain the existing database uniqueness rules. The adapter exposes no deletion,
ledger edits, arbitrary URLs, owner overrides, photo analysis, or bulk writes.

## Configuration

| Environment variable | Value |
| --- | --- |
| `DJANGO_API_BASE_URL` | `https://wiest.world/django/demos/inventory/api/` |
| `DJANGO_API_AUTHORIZATION` | `Basic ` followed by Base64 of `username:password` |
| `MCP_AUTH_TOKEN` | A separate strong random token for MCP callers |
| `MCP_PATH` | Optional; defaults to `/api/inventory-mcp` |
| `PUBLIC_HOST` | Public hostname serving MCP, e.g. `wiest.world` |

Both authentication values are secrets: keep them out of git and client-visible
configuration. Set them through your existing secure Lambda configuration
process. The inbound MCP bearer token is separate from outbound Django Basic
Auth. Anyone with that MCP token can act as the configured Django user; this is
a single-account integration, not delegated multi-user OAuth. Missing inbound
token configuration fails closed with 503; incorrect/missing bearer auth returns
401. Requests and API credentials are not logged.

Ensure the Django login middleware lets the Inventory API reach DRF, as with
your working Postman requests. DRF still authenticates and scopes every request.
Login redirects are rejected rather than followed. There are no automatic HTTP
retries; upstream errors appear as MCP tool errors with HTTP status and a short
sanitized message. A timeout does not prove a write failed.

## Build and deploy

From this directory:

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m unittest discover -s . -v
.venv/bin/python build.py
```

Build writes `dist/inventory-mcp-lambda.zip`, including Linux CPython 3.12 x86_64
dependencies, independent of the build host. Upload the ZIP to a separate Lambda:

- Runtime: Python 3.12; architecture: x86_64.
- Handler: `lambda_function.lambda_handler`.
- Suggested initial memory: 256 MB; timeout: 30 seconds (Django HTTP timeout is 20).
- Configure the variables above and allow outbound HTTPS to Django.
- Add `POST /api/inventory-mcp` to your API Gateway HTTP API, using Lambda proxy
  integration with payload format 2.0 and permission to invoke this function.
- If using your existing CloudFront front door, route that path to the API
  Gateway origin, disable caching, forward `Authorization`, `Accept`,
  `Content-Type`, `MCP-Protocol-Version`, and `Origin`, and preserve the path.
- Set `PUBLIC_HOST` to the hostname clients connect to, without scheme or path.
  The API Gateway domain is also accepted for transport host checks.

This code adds no infrastructure or deployment actions to the EC2 workflow.
Deploying the normal Django wheel does not deploy this Lambda.

## Connect and smoke test

Point a Streamable HTTP MCP client at your deployed URL, with this header:

```text
Authorization: Bearer <MCP_AUTH_TOKEN>
```

For a client supporting custom headers, configure its remote server URL as
`https://wiest.world/api/inventory-mcp` (or the host you deployed). Clients that
only support OAuth will need a separate OAuth integration; this adapter uses a
configured bearer token, not an OAuth authorization flow.

First initialize and list tools, then call `search_inventory_lists` and
`search_inventory_items`. Those reads verify the connection without changing
stock. Writes in the deployed server modify real inventory.

Example tool call arguments for `adjust_inventory_quantity`:

```json
{
  "entry_id": 42,
  "operation": "add",
  "quantity": 3,
  "idempotency_key": "grocery-trip-123-entry-42",
  "reference_id": "grocery-trip-123",
  "metadata": {"confidence": 0.92}
}
```

Use an entry ID returned by search. The server fixes transaction `source` to
`mcp`. Repeat the identical call with the same key to safely retry; the API
returns the original event without adding stock twice. A new intended adjustment
needs a new key. `remove` cannot make stock negative. `set` replaces the balance
and should only follow explicit review/approval. Pantry photos show partial
observations and must not silently zero unseen stock.

Catalog/list/entry creation is **not idempotent**. Search first; after an
uncertain creation response, inspect existing records before retrying. Multiple
entries for the same item/list are allowed by the existing API. Tool annotations
reflect this distinction. Updating catalog fields never changes quantities.

## Validation

The isolated tests exercise actual MCP initialize, tools/list and tools/call
requests through the Lambda handler, schema validation, API route mapping,
partial updates, retry payload preservation, authentication, redirect rejection,
and request size limits. Django HTTP is mocked; these tests do not claim live
AWS, CloudFront, credentials, or production inventory validation.
