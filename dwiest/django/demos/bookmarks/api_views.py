"""REST API views for the bookmarks application.

Drop this into demos/bookmarks/api_views.py. The owner is resolved from the
temporary BOOKMARKS_API_OWNER_ID setting, matching the existing private API.
"""
from datetime import datetime, time

from django.conf import settings as django_settings
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Bookmark, BookmarkTag, Tag


def get_api_owner(request):
    """Resolve the configured owner for this temporary private-test API."""
    from django.contrib.auth import get_user_model

    owner_id = getattr(django_settings, "BOOKMARKS_API_OWNER_ID", None)
    if not owner_id:
        return None
    try:
        return get_user_model().objects.get(pk=owner_id)
    except get_user_model().DoesNotExist:
        raise ValidationError("BOOKMARKS_API_OWNER_ID does not identify a user.")


def _bookmark_queryset(owner):
    return Bookmark.objects.filter(owner=owner)


def _tag_titles(bookmark):
    return list(Tag.objects.filter(
        owner=bookmark.owner, bookmarktag__bookmark=bookmark,
    ).order_by("title").values_list("title", flat=True).distinct())


def serialize_bookmark(bookmark):
    article_date = bookmark.article_date
    if article_date and timezone.is_aware(article_date):
        article_date = timezone.localtime(article_date)
    return {
        "id": bookmark.id,
        "url": bookmark.url,
        "title": bookmark.title,
        "article_date": article_date.isoformat() if article_date else None,
        "description": bookmark.description,
        "tags": _tag_titles(bookmark),
        "status": bookmark.status,
        "unread": bookmark.unread,
    }


def _parse_article_date(value):
    if value is None or value == "":
        return None
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        raise ValidationError({"article_date": "Use YYYY-MM-DD, or null."})
    result = datetime.combine(parsed, time.min)
    if timezone.is_aware(timezone.now()):
        result = timezone.make_aware(result, timezone.get_current_timezone())
    return result


def _parse_tag_ids(value):
    if not isinstance(value, list) or any(isinstance(i, bool) or not isinstance(i, int) for i in value):
        raise ValidationError({"tag_ids": "Expected a list of integer tag IDs."})
    if len(set(value)) != len(value):
        raise ValidationError({"tag_ids": "Duplicate tag IDs are not allowed."})
    return value


def _owned_tags(owner, tag_ids):
    tags = list(Tag.objects.filter(owner=owner, id__in=tag_ids))
    if len(tags) != len(tag_ids):
        raise ValidationError({"tag_ids": "One or more tags were not found for this owner."})
    return tags


def _set_tags(bookmark, owner, tag_ids, replace=True):
    tags = _owned_tags(owner, tag_ids)
    if replace:
        BookmarkTag.objects.filter(owner=owner, bookmark=bookmark).exclude(tag__in=tags).delete()
    for tag in tags:
        BookmarkTag.objects.get_or_create(owner=owner, bookmark=bookmark, tag=tag)


def _update_bookmark(bookmark, request, partial):
    allowed = {"url", "title", "description", "article_date", "tag_ids", "status", "unread"}
    unknown = set(request.data.keys()) - allowed
    if unknown:
        raise ValidationError({key: "Unknown field." for key in sorted(unknown)})
    if not partial:
        required = {"url", "title", "description", "article_date"}
        missing = required - set(request.data.keys())
        if missing:
            raise ValidationError({key: "This field is required." for key in sorted(missing)})

    data = request.data
    if "url" in data:
        url = data["url"]
        if not isinstance(url, str) or not url.strip():
            raise ValidationError({"url": "A non-empty URL is required."})
        bookmark.url = url.strip()
    if "title" in data:
        if not isinstance(data["title"], str):
            raise ValidationError({"title": "Expected a string."})
        bookmark.title = data["title"].strip()
    if "description" in data:
        if data["description"] is not None and not isinstance(data["description"], str):
            raise ValidationError({"description": "Expected a string or null."})
        bookmark.description = data["description"] or ""
    if "article_date" in data:
        bookmark.article_date = _parse_article_date(data["article_date"])
    if "status" in data:
        if type(data["status"]) is not int or data["status"] not in (-1, 0, 1):
            raise ValidationError({"status": "Use -1, 0, or 1."})
        bookmark.status = data["status"]
    if "unread" in data:
        if type(data["unread"]) is not bool:
            raise ValidationError({"unread": "Expected a boolean."})
        bookmark.unread = data["unread"]
    tag_ids = _parse_tag_ids(data["tag_ids"]) if "tag_ids" in data else None

    try:
        with transaction.atomic():
            bookmark.save()
            if tag_ids is not None:
                _set_tags(bookmark, bookmark.owner, tag_ids)
    except IntegrityError:
        raise ValidationError({"url": "A bookmark with this URL already exists."})
    return bookmark


class BookmarkPagination(PageNumberPagination):
    page_size = 40
    page_size_query_param = "page_size"
    max_page_size = 100


class BookmarkLookupAPIView(APIView):
    def get(self, request):
        url = request.query_params.get("url")
        if not url:
            raise ValidationError({"url": "This query parameter is required."})
        owner = get_api_owner(request)
        bookmark = _bookmark_queryset(owner).filter(url=url).first()
        if bookmark is None:
            return Response({"exists": False, "url": url})
        return Response({"exists": True, "bookmark": serialize_bookmark(bookmark)})


def serialize_tag(tag):
    return {"id": tag.id, "title": tag.title,
            "description": tag.description, "style": tag.style}


def validate_tag_data(data, partial=False):
    allowed = {"title", "description", "style"}
    unknown = set(data.keys()) - allowed
    if unknown:
        raise ValidationError({key: "Unknown field." for key in unknown})
    if not partial and "title" not in data:
        raise ValidationError({"title": "This field is required."})
    values = {}
    for key in allowed.intersection(data.keys()):
        value = data[key]
        if key == "description" and value is None:
            values[key] = value
            continue
        if not isinstance(value, str):
            raise ValidationError({key: "Expected a string."})
        if key in ("title", "style") and len(value) > 255:
            raise ValidationError({key: "Use at most 255 characters."})
        if key == "title":
            value = value.strip()
            if not value:
                raise ValidationError({key: "A non-empty title is required."})
        values[key] = value
    return values


class TagDetailAPIView(APIView):
    def get(self, request, tag_id):
        tag = get_object_or_404(Tag, owner=get_api_owner(request), pk=tag_id)
        return Response(serialize_tag(tag))

    def patch(self, request, tag_id):
        tag = get_object_or_404(Tag, owner=get_api_owner(request), pk=tag_id)
        for key, value in validate_tag_data(request.data, partial=True).items():
            setattr(tag, key, value)
        tag.save()
        return Response(serialize_tag(tag))


class TagListAPIView(APIView):
    def post(self, request):
        values = validate_tag_data(request.data)
        values.setdefault("style", "")
        tag = Tag.objects.create(owner=get_api_owner(request), **values)
        return Response(serialize_tag(tag), status=status.HTTP_201_CREATED)

    def get(self, request):
        owner = get_api_owner(request)
        tags = Tag.objects.filter(owner=owner).order_by("title")
        return Response({"tags": [{"id": t.id, "title": t.title} for t in tags]})


class BookmarkCreateAPIView(APIView):
    def get(self, request):
        owner = get_api_owner(request)
        qs = _bookmark_queryset(owner)
        term = request.query_params.get("term", "").strip()
        field = request.query_params.get("field", "all")
        valid_fields = {"title", "description", "url", "all"}
        if field not in valid_fields:
            raise ValidationError({"field": "Use title, description, url, or all."})
        if term:
            q = Q()
            fields = ["title", "description", "url"] if field == "all" else [field]
            for name in fields:
                q |= Q(**{name + "__icontains": term})
            qs = qs.filter(q)

        filter_name = request.query_params.get("filter", "none")
        if filter_name not in {"none", "undated", "untitled", "date"}:
            raise ValidationError({"filter": "Use none, undated, untitled, or date."})
        if filter_name == "undated":
            qs = qs.filter(article_date__isnull=True)
        elif filter_name == "untitled":
            qs = qs.filter(title="")
        elif filter_name == "date":
            year = request.query_params.get("year")
            month = request.query_params.get("month")
            try:
                year = int(year)
                month = int(month) if month not in (None, "", "0") else None
                if month is not None and not 1 <= month <= 12:
                    raise ValueError()
            except (TypeError, ValueError):
                raise ValidationError({"date": "For filter=date provide a valid year and optional month 1-12."})
            qs = qs.filter(article_date__year=year)
            if month:
                qs = qs.filter(article_date__month=month)

        show_deleted = request.query_params.get("show_deleted", "false").lower() in ("1", "true", "yes")
        show_hidden = request.query_params.get("show_hidden", "false").lower() in ("1", "true", "yes")
        hide_read = request.query_params.get("hide_read", "false").lower() in ("1", "true", "yes")
        statuses = [0] + ([-1] if show_deleted else []) + ([1] if show_hidden else [])
        qs = qs.filter(status__in=statuses)
        if hide_read:
            qs = qs.filter(unread=True)
        tag_id = request.query_params.get("tag_id")
        if tag_id:
            try:
                tag_id = int(tag_id)
            except ValueError:
                raise ValidationError({"tag_id": "Expected an integer tag ID."})
            qs = qs.filter(bookmarktag__owner=owner, bookmarktag__tag_id=tag_id)
        qs = qs.distinct().order_by("-article_date", "-id")
        paginator = BookmarkPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        return paginator.get_paginated_response([serialize_bookmark(b) for b in page])

    def post(self, request):
        # Import locally because batch_api shares owner/date/serialization helpers.
        from .batch_api import compact_query, create_one
        compact = compact_query(request)
        bookmark, outcome = create_one(get_api_owner(request), request.data)
        if compact:
            body = {"id": bookmark.pk, "outcome": outcome}
        elif outcome == "existing":
            body = {"error": "bookmark_exists", "bookmark": serialize_bookmark(bookmark)}
        else:
            body = serialize_bookmark(bookmark)
        return Response(body, status=(status.HTTP_201_CREATED if outcome == "created"
                                      else status.HTTP_409_CONFLICT))


class BookmarkDetailAPIView(APIView):
    def _get(self, request, bookmark_id):
        return get_object_or_404(_bookmark_queryset(get_api_owner(request)), id=bookmark_id)

    def get(self, request, bookmark_id):
        return Response(serialize_bookmark(self._get(request, bookmark_id)))

    def delete(self, request, bookmark_id):
        bookmark = self._get(request, bookmark_id)
        bookmark.status = -1
        bookmark.save(update_fields=["status", "last_modified"])
        return Response(status=status.HTTP_204_NO_CONTENT)

    def patch(self, request, bookmark_id):
        bookmark = _update_bookmark(self._get(request, bookmark_id), request, partial=True)
        return Response(serialize_bookmark(bookmark))

    def put(self, request, bookmark_id):
        bookmark = _update_bookmark(self._get(request, bookmark_id), request, partial=False)
        return Response(serialize_bookmark(bookmark))


class BookmarkTagListAPIView(APIView):
    def _bookmark(self, request, bookmark_id):
        return get_object_or_404(_bookmark_queryset(get_api_owner(request)), id=bookmark_id)

    def get(self, request, bookmark_id):
        bookmark = self._bookmark(request, bookmark_id)
        qs = Tag.objects.filter(owner=bookmark.owner, bookmarktag__bookmark=bookmark).distinct().order_by("title")
        return Response({"tags": [{"id": t.id, "title": t.title} for t in qs]})

    def post(self, request, bookmark_id):
        bookmark = self._bookmark(request, bookmark_id)
        tag_ids = _parse_tag_ids(request.data.get("tag_ids"))
        with transaction.atomic():
            _set_tags(bookmark, bookmark.owner, tag_ids, replace=False)
        return Response(serialize_bookmark(bookmark))

    def put(self, request, bookmark_id):
        bookmark = self._bookmark(request, bookmark_id)
        tag_ids = _parse_tag_ids(request.data.get("tag_ids"))
        with transaction.atomic():
            _set_tags(bookmark, bookmark.owner, tag_ids, replace=True)
        return Response(serialize_bookmark(bookmark))


class BookmarkTagDetailAPIView(APIView):
    def delete(self, request, bookmark_id, tag_id):
        owner = get_api_owner(request)
        bookmark = get_object_or_404(_bookmark_queryset(owner), id=bookmark_id)
        association = get_object_or_404(BookmarkTag, owner=owner, bookmark=bookmark, tag_id=tag_id)
        association.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

