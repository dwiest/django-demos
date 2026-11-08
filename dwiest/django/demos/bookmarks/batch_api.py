"""Bounded batch operations; no schema migration or external requests."""
import json
import logging
import time
import uuid

from django.db import DatabaseError, IntegrityError, transaction
from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework import serializers, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .api_views import get_api_owner, serialize_bookmark, _parse_article_date
from .models import Bookmark, BookmarkTag, Tag

logger = logging.getLogger("bookmarks.batch")
MAX_ITEMS = 50
MAX_BODY_BYTES = 1024 * 1024


class StrictSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        if not isinstance(data, dict):
            raise ValidationError("Expected a JSON object.")
        unknown = set(data) - set(self.fields)
        if unknown:
            raise ValidationError({key: "Unknown field." for key in sorted(unknown)})
        return super().to_internal_value(data)


class StrictInteger(serializers.IntegerField):
    def to_internal_value(self, data):
        if type(data) is not int:
            self.fail("invalid")
        return super().to_internal_value(data)


class StrictBoolean(serializers.BooleanField):
    def to_internal_value(self, data):
        if type(data) is not bool:
            self.fail("invalid")
        return data


class StrictString(serializers.CharField):
    def to_internal_value(self, data):
        if not isinstance(data, str):
            self.fail("invalid")
        return super().to_internal_value(data)


class BookmarkInput(StrictSerializer):
    url = serializers.URLField(max_length=255)
    title = StrictString(max_length=255)
    description = StrictString(required=False, default="", allow_null=True, allow_blank=True,
                               trim_whitespace=False)
    article_date = serializers.DateField(required=False, allow_null=True,
                                         input_formats=["%Y-%m-%d"])
    tag_ids = serializers.ListField(child=StrictInteger(min_value=1), required=False,
                                    max_length=200)
    tags = serializers.ListField(child=StrictString(max_length=255), required=False,
                                 max_length=200)
    status = StrictInteger(required=False)
    unread = StrictBoolean(required=False)

    def validate_status(self, value):
        if value not in (-1, 0, 1):
            raise ValidationError("Use -1, 0, or 1.")
        return value

    def validate_tag_ids(self, value):
        if len(value) != len(set(value)):
            raise ValidationError("Duplicate tag IDs are not allowed.")
        return value

    def validate(self, data):
        if "tags" in data and "tag_ids" in data:
            raise ValidationError("Supply either tags or tag_ids, not both.")
        return data


class UpdateInput(BookmarkInput):
    description = StrictString(required=False, allow_null=True, allow_blank=True,
                               trim_whitespace=False)
    url = serializers.URLField(required=False, max_length=255)
    title = StrictString(required=False, allow_blank=True, max_length=255)
    tags = None

    def validate(self, data):
        if not data:
            raise ValidationError("Provide at least one change.")
        return data


class URLInput(StrictSerializer):
    url = serializers.URLField(max_length=255)


def owned_tags(owner, ids):
    tags = list(Tag.objects.filter(owner=owner, pk__in=ids))
    if len(tags) != len(ids):
        raise ValidationError({"tag_ids": "One or more tags were not found for this owner."})
    return tags


def assign_tags(bookmark, owner, tags):
    BookmarkTag.objects.filter(bookmark=bookmark, owner=owner).delete()
    BookmarkTag.objects.bulk_create([
        BookmarkTag(owner=owner, bookmark=bookmark, tag=tag) for tag in tags
    ])


def field_values(data):
    values = {key: value for key, value in data.items() if key not in ("tags", "tag_ids")}
    if "article_date" in values and values["article_date"] is not None:
        values["article_date"] = _parse_article_date(values["article_date"].isoformat())
    return values


def create_one(owner, raw):
    validator = BookmarkInput(data=raw)
    validator.is_valid(raise_exception=True)
    data = validator.validated_data
    existing = Bookmark.objects.filter(owner=owner, url=data["url"]).first()
    if existing:
        return existing, "existing"
    try:
        with transaction.atomic():
            tags = owned_tags(owner, data["tag_ids"]) if "tag_ids" in data else []
            for title in dict.fromkeys(data.get("tags", [])):
                # Legacy title input remains supported, but never chooses an
                # arbitrary tag when existing names are ambiguous.
                matches = list(Tag.objects.filter(owner=owner, title=title)[:2])
                if len(matches) > 1:
                    raise ValidationError({"tags": "Ambiguous tag title; use tag_ids."})
                tags.append(matches[0] if matches else Tag.objects.create(
                    owner=owner, title=title, style=""))
            bookmark = Bookmark.objects.create(owner=owner, **field_values(data))
            assign_tags(bookmark, owner, tags)
            return bookmark, "created"
    except IntegrityError:
        # Query only after rollback; never disclose another owner's record.
        existing = Bookmark.objects.filter(owner=owner, url=data["url"]).first()
        if existing:
            return existing, "existing"
        raise ValidationError({"url": "URL conflicts with an existing record."})


def update_one(owner, bookmark_id, raw):
    validator = UpdateInput(data=raw)
    validator.is_valid(raise_exception=True)
    data = validator.validated_data
    try:
        with transaction.atomic():
            bookmark = get_object_or_404(Bookmark.objects.select_for_update(),
                                         owner=owner, pk=bookmark_id)
            tags = owned_tags(owner, data["tag_ids"]) if "tag_ids" in data else None
            values = field_values(data)
            for key, value in values.items():
                setattr(bookmark, key, value)
            # Write only submitted columns to avoid clobbering concurrent changes.
            if values:
                bookmark.save(update_fields=list(values) + ["last_modified"])
            elif tags is not None:
                bookmark.save(update_fields=["last_modified"])
            if tags is not None:
                assign_tags(bookmark, owner, tags)
            return bookmark, "updated"
    except IntegrityError:
        raise ValidationError({"url": "URL conflicts with an existing record."})


def compact_query(request):
    value = request.query_params.get("compact", "false").lower()
    if value not in ("true", "false", "1", "0"):
        raise ValidationError({"compact": "Use true or false."})
    return value in ("true", "1")


class BulkBase(APIView):
    operation = None

    def initial(self, request, *args, **kwargs):
        self.started = time.monotonic()
        self.attempt_id = str(uuid.uuid4())
        self.batch_id = None
        self.submitted = 0
        super().initial(request, *args, **kwargs)
        # CONTENT_LENGTH also protects requests before JSON parsing. The server
        # must enforce its own limit for chunked bodies, as documented.
        length = request.META.get("CONTENT_LENGTH")
        if length and int(length) > MAX_BODY_BYTES:
            from rest_framework.exceptions import APIException
            exc = APIException("Batch body exceeds 1 MiB.")
            exc.status_code = 413
            raise exc

    def envelope(self, request):
        body = request.data
        if not isinstance(body, dict):
            raise ValidationError("Expected an object containing items.")
        if set(body) - {"batch_id", "items", "compact"}:
            raise ValidationError("Unknown batch field.")
        batch_id = body.get("batch_id", self.attempt_id)
        if not isinstance(batch_id, str) or not batch_id or len(batch_id) > 100:
            raise ValidationError({"batch_id": "Use a non-empty string of at most 100 characters."})
        # batch_id/client_ref are untrusted correlation values, not idempotency keys.
        self.batch_id = batch_id
        items = body.get("items")
        if not isinstance(items, list) or not 1 <= len(items) <= MAX_ITEMS:
            raise ValidationError({"items": "Provide 1 to 50 items."})
        self.submitted = len(items)
        compact = body.get("compact", True)
        if type(compact) is not bool:
            raise ValidationError({"compact": "Expected a boolean."})
        refs = set()
        for item in items:
            if not isinstance(item, dict):
                raise ValidationError({"items": "Each item must be an object with client_ref."})
            ref = item.get("client_ref")
            if not isinstance(ref, str) or not ref or len(ref) > 100 or ref in refs:
                raise ValidationError({"client_ref": "Provide unique non-empty strings, maximum 100 characters."})
            refs.add(ref)
        return items, compact

    def item_result(self, ref, bookmark, outcome, compact):
        result = {"client_ref": ref, "outcome": outcome}
        if bookmark is not None:
            result["id"] = bookmark.pk
            if not compact:
                result["bookmark"] = serialize_bookmark(bookmark)
        return result

    def finish(self, results):
        counts = {key: 0 for key in ("created", "existing", "updated", "missing", "failed")}
        for result in results:
            counts[result["outcome"]] += 1
        return Response({"batch_id": self.batch_id, "attempt_id": self.attempt_id,
                         "counts": counts, "results": results})

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        data = getattr(response, "data", {})
        if not isinstance(data, dict):
            data = {}
        logger.info(json.dumps({
            "event": "bookmark_batch", "operation": self.operation,
            "batch_id": getattr(self, "batch_id", None),
            "attempt_id": getattr(self, "attempt_id", None),
            "submitted": getattr(self, "submitted", 0), "counts": data.get("counts", {}),
            "http_status": response.status_code,
            "duration_ms": round((time.monotonic() - getattr(self, "started", time.monotonic())) * 1000, 2),
        }))
        return response


class BulkLookupAPIView(BulkBase):
    operation = "lookup"

    def post(self, request):
        items, compact = self.envelope(request)
        owner = get_api_owner(request)
        valid, errors = {}, {}
        for item in items:
            ref = item["client_ref"]
            validator = URLInput(data={k: v for k, v in item.items() if k != "client_ref"})
            if validator.is_valid():
                valid[ref] = validator.validated_data["url"]
            else:
                errors[ref] = validator.errors
        # One bookmark query for the entire URL list, including repeats.
        found = {b.url: b for b in Bookmark.objects.filter(owner=owner, url__in=set(valid.values()))}
        results = []
        for item in items:
            ref = item["client_ref"]
            if ref in errors:
                results.append({"client_ref": ref, "outcome": "failed", "errors": errors[ref]})
            else:
                bookmark = found.get(valid[ref])
                results.append(self.item_result(ref, bookmark, "existing" if bookmark else "missing", compact))
        return self.finish(results)


class BulkWriteBase(BulkBase):
    def run(self, request):
        items, compact = self.envelope(request)
        owner = get_api_owner(request)
        results = []
        for item in items:
            ref = item["client_ref"]
            try:
                bookmark, outcome = self.process(owner, item)
                results.append(self.item_result(ref, bookmark, outcome, compact))
            except ValidationError as exc:
                results.append({"client_ref": ref, "outcome": "failed", "errors": exc.detail})
            except Http404:
                results.append({"client_ref": ref, "outcome": "failed", "errors": {"id": "Bookmark not found."}})
            except DatabaseError:
                # No raw database exceptions or submitted content in logs/results.
                results.append({"client_ref": ref, "outcome": "failed", "errors": {"database": "Database operation failed; retry this item."}})
        return self.finish(results)


class BulkCreateAPIView(BulkWriteBase):
    operation = "create"

    def post(self, request):
        return self.run(request)

    def process(self, owner, item):
        return create_one(owner, {k: v for k, v in item.items() if k != "client_ref"})


class BulkUpdateAPIView(BulkWriteBase):
    operation = "update"

    def patch(self, request):
        return self.run(request)

    def process(self, owner, item):
        if set(item) != {"client_ref", "id", "changes"}:
            raise ValidationError("Each update needs client_ref, id, and changes only.")
        bookmark_id = item["id"]
        if type(bookmark_id) is not int or bookmark_id < 1:
            raise ValidationError({"id": "Expected a positive integer."})
        return update_one(owner, bookmark_id, item["changes"])
