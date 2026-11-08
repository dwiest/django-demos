"""Server-rendered browser UI. Existing MCP/REST endpoints are unchanged."""
from urllib.parse import urlsplit
from django.contrib import messages
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.db.models import Q, Prefetch, Count
from django.http import Http404, HttpResponseRedirect, JsonResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, render, reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View
from .models import Bookmark, BookmarkTag, Tag
from .ui_forms import BookmarkEditorForm, BookmarkQueryForm, TagEditorForm, TagQueryForm

from .ui_tags import tag_tone

ROOT = 'dwiest-django-demos/bookmarks/'


def legacy_id(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        raise Http404('Record not found')


def owner_for(request):
    # Preserve the existing browser application's anonymous owner=None behavior.
    return request.user if request.user.is_authenticated else None


def return_url(request):
    fallback = reverse('demos:bookmarks:home')
    value = request.POST.get('next') or request.GET.get('next') or fallback
    return value if url_has_allowed_host_and_scheme(value, {request.get_host()}, require_https=request.is_secure()) else fallback


def display_url(url):
    try:
        parsed = urlsplit(url)
        return url if parsed.scheme in ('http', 'https') and parsed.netloc else ''
    except ValueError:
        return ''


class BookmarksUI(View):
    def get(self, request):
        owner = owner_for(request)
        form = BookmarkQueryForm(request.GET or {'field': 'all', 'filter': 'none', 'page_size': 40}, owner=owner)
        bookmarks = Bookmark.objects.filter(owner=owner)
        valid = form.is_valid()
        data = form.cleaned_data
        if valid:
            term = data.get('term')
            if term:
                fields = ('title', 'description', 'url') if data.get('field') in ('', 'all') else (data['field'],)
                q = Q()
                for field in fields:
                    q |= Q(**{field + '__icontains': term})
                bookmarks = bookmarks.filter(q)
            mode = data.get('filter')
            if mode == 'untitled':
                bookmarks = bookmarks.filter(title='')
            elif mode == 'undated':
                bookmarks = bookmarks.filter(article_date__isnull=True)
            elif mode == 'date':
                bookmarks = bookmarks.filter(article_date__year=data['year'])
                if data.get('month'):
                    bookmarks = bookmarks.filter(article_date__month=data['month'])
            statuses = [0] + ([1] if data.get('show_hidden') else []) + ([-1] if data.get('show_deleted') else [])
            bookmarks = bookmarks.filter(status=-1) if data.get('deleted_only') else bookmarks.filter(status__in=statuses)
            if data.get('hide_read'):
                bookmarks = bookmarks.filter(unread=True)
            # Separate joins implement intersection: every selected tag must match.
            for tag in data.get('tag_id', []):
                bookmarks = bookmarks.filter(bookmarktag__owner=owner, bookmarktag__tag=tag)
        else:
            bookmarks = bookmarks.none()
        bookmarks = bookmarks.distinct().order_by('-article_date', '-id').prefetch_related(Prefetch('bookmarktag_set', queryset=BookmarkTag.objects.filter(owner=owner).select_related('tag'), to_attr='ui_tag_links'))
        from django.core.paginator import Paginator
        page = Paginator(bookmarks, data.get('page_size') or 40).get_page(request.GET.get('page'))
        for bookmark in page:
            bookmark.ui_url = display_url(bookmark.url)
            try:
                bookmark.domain = urlsplit(bookmark.url).hostname or bookmark.url
            except ValueError:
                bookmark.domain = bookmark.url
            bookmark.ui_tags = [link.tag for link in bookmark.ui_tag_links]
            for tag in bookmark.ui_tags:
                tag.ui_tone = tag_tone(tag)
                tag_params = request.GET.copy()
                tag_params.pop('page', None)
                tag_params.setlist('tag_id', list(dict.fromkeys(tag_params.getlist('tag_id') + [str(tag.pk)])))
                tag.filter_url = '?' + tag_params.urlencode()
        params = request.GET.copy()
        params.pop('page', None)
        chips = []
        selected_tags = list(data.get('tag_id', [])) if valid else []
        labels = {'term': 'Search: ' + data.get('term', ''), 'filter': dict(form.fields['filter'].choices).get(data.get('filter')), 'hide_read': 'Unread only', 'show_hidden': 'Including hidden', 'show_deleted': 'Including deleted', 'deleted_only': 'Deleted only'}
        if data.get('filter') == 'date':
            labels['filter'] = 'Publication date: ' + str(data.get('year', '')) + (' / ' + str(data['month']) if data.get('month') else '')
        for key, label in labels.items():
            if data.get(key) and not (key == 'filter' and data[key] == 'none'):
                cleared = params.copy()
                cleared.pop(key, None)
                chips.append({'label': label, 'url': '?' + cleared.urlencode()})
        for tag in selected_tags:
            cleared = params.copy()
            remaining = [str(item.pk) for item in selected_tags if item.pk != tag.pk]
            cleared.pop('tag_id', None)
            if remaining:
                cleared.setlist('tag_id', remaining)
            chips.append({'label': tag.title, 'url': '?' + cleared.urlencode()})
        return render(request, ROOT + 'home.html', {'query': form, 'page_obj': page, 'page_query': params.urlencode(), 'chips': chips, 'filters_open': not valid, 'next_url': request.get_full_path(), 'selected_tag': selected_tags[0] if len(selected_tags) == 1 else None, 'selected_tags': selected_tags, 'deleted_only': bool(data.get('deleted_only'))})


class BookmarkEditorUI(View):
    def bookmark(self, request):
        bookmark_id = request.POST.get('id') if request.method == 'POST' else request.GET.get('id')
        if bookmark_id:
            try:
                bookmark_id = int(bookmark_id)
            except (TypeError, ValueError):
                raise Http404('Bookmark not found')
            return get_object_or_404(Bookmark, owner=owner_for(request), pk=bookmark_id)
        return Bookmark(owner=owner_for(request))

    def context(self, request, form):
        # Baseline is persisted state, so a validation response can still reset correctly.
        original = BookmarkEditorForm(instance=self.bookmark(request), owner=owner_for(request))
        baseline = {name: str(original[name].value() or '') for name in ('url', 'title', 'description', 'article_date', 'status')}
        baseline['article_date'] = original.instance.article_date.strftime('%Y-%m-%d') if original.instance.article_date else ''
        baseline['status'] = str(original.instance.status)
        baseline['unread'] = bool(original.instance.unread)
        baseline['tag_ids'] = [str(i) for i in original.initial.get('tag_ids', [])]
        return {'form': form, 'next_url': return_url(request), 'baseline': baseline, 'bookmark_url': display_url(form['url'].value() or '')}

    def get(self, request):
        form = BookmarkEditorForm(instance=self.bookmark(request), owner=owner_for(request))
        return render(request, ROOT + 'bookmark.html', self.context(request, form))

    def post(self, request):
        instance = self.bookmark(request)
        form = BookmarkEditorForm(request.POST, instance=instance, owner=owner_for(request))
        if form.is_valid():
            try:
                with transaction.atomic():
                    bookmark = form.save(commit=False)
                    bookmark.owner = owner_for(request)
                    bookmark.save()
                    tags = form.cleaned_data['tag_ids']
                    BookmarkTag.objects.filter(owner=bookmark.owner, bookmark=bookmark).exclude(tag__in=tags).delete()
                    for tag in tags:
                        BookmarkTag.objects.get_or_create(owner=bookmark.owner, bookmark=bookmark, tag=tag)
            except IntegrityError:
                form.add_error(None, 'Could not save this bookmark. Its URL may already exist. Your changes are still here.')
            else:
                messages.success(request, 'Bookmark saved.')
                return HttpResponseRedirect(return_url(request))
        return render(request, ROOT + 'bookmark.html', self.context(request, form))


class BookmarkActionUI(View):
    def post(self, request, bookmark_id):
        bookmark = get_object_or_404(Bookmark, owner=owner_for(request), pk=bookmark_id)
        action = request.POST.get('action')
        if action == 'read':
            bookmark.unread = False
        elif action == 'unread':
            bookmark.unread = True
        elif action == 'hide':
            bookmark.status = 1
        elif action == 'delete':
            bookmark.status = -1
        elif action == 'restore':
            bookmark.status = 0
        else:
            return JsonResponse({'error': 'Unknown action'}, status=400)
        bookmark.save(update_fields=['unread', 'status', 'last_modified'])
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'unread': bookmark.unread, 'status': bookmark.status})
        return HttpResponseRedirect(return_url(request))


class TagsUI(View):
    def get(self, request):
        owner = owner_for(request)
        form = TagQueryForm(request.GET or {'sort': 'name', 'page_size': 20})
        tags = Tag.objects.filter(owner=owner)
        if form.is_valid():
            term = form.cleaned_data.get('term')
            if term:
                tags = tags.filter(Q(title__icontains=term) | Q(description__icontains=term))
        else:
            tags = tags.none()
        # Count active bookmarks only, matching the destination's default filter.
        tags = tags.annotate(bookmark_count=Count('bookmarktag__bookmark', filter=Q(bookmarktag__owner=owner, bookmarktag__bookmark__owner=owner, bookmarktag__bookmark__status=0), distinct=True))
        tags = tags.order_by('-bookmark_count', 'title', 'id') if form.cleaned_data.get('sort') == 'count' else tags.order_by('title', 'id')
        from django.core.paginator import Paginator
        page = Paginator(tags, form.cleaned_data.get('page_size') or 20).get_page(request.GET.get('page'))
        for tag in page:
            tag.ui_tone = tag_tone(tag)
        params = request.GET.copy()
        params.pop('page', None)
        return render(request, ROOT + 'tags/index.html', {'query': form, 'page_obj': page, 'page_query': params.urlencode(), 'next_url': request.get_full_path(), 'nav_section': 'tags', 'page_item_label': 'Tags'})


class TagEditorUI(View):
    def tag(self, request):
        value = request.POST.get('id') if request.method == 'POST' else request.GET.get('id')
        if not value:
            return Tag(owner=owner_for(request))
        try:
            value = int(value)
        except (TypeError, ValueError):
            raise Http404('Tag not found')
        return get_object_or_404(Tag, owner=owner_for(request), pk=value)

    def destination(self, request):
        fallback = reverse('demos:bookmarks:tags')
        value = request.POST.get('next') or request.GET.get('next') or fallback
        return value if url_has_allowed_host_and_scheme(value, {request.get_host()}, require_https=request.is_secure()) else fallback

    def context(self, request, form):
        original = self.tag(request)
        appearance = original.style if original.style in ('', 'ui:0', 'ui:1', 'ui:2', 'ui:3', 'ui:4', 'ui:5') else 'legacy'
        return {'form': form, 'next_url': self.destination(request), 'nav_section': 'tags', 'baseline': {'title': original.title or '', 'description': original.description or '', 'appearance': appearance}, 'preview_tone': tag_tone(original)}

    def get(self, request):
        form = TagEditorForm(instance=self.tag(request), owner=owner_for(request))
        return render(request, ROOT + 'tags/edit.html', self.context(request, form))

    def post(self, request):
        form = TagEditorForm(request.POST, instance=self.tag(request), owner=owner_for(request))
        if form.is_valid():
            with transaction.atomic():
                form.save()
            messages.success(request, 'Tag saved.')
            return HttpResponseRedirect(self.destination(request))
        return render(request, ROOT + 'tags/edit.html', self.context(request, form))


class LegacyTagRedirectUI(View):
    def get(self, request):
        tag = get_object_or_404(Tag, owner=owner_for(request), pk=legacy_id(request.GET.get('id')))
        return HttpResponseRedirect(reverse('demos:bookmarks:home') + '?tag_id=' + str(tag.pk))


class LegacyBookmarkTagRedirectUI(View):
    def get(self, request):
        value = request.GET.get('id')
        if value:
            link = get_object_or_404(BookmarkTag, owner=owner_for(request), pk=legacy_id(value), bookmark__owner=owner_for(request))
            bookmark = link.bookmark
        else:
            bookmark = get_object_or_404(Bookmark, owner=owner_for(request), pk=legacy_id(request.GET.get('bookmark_id')))
        return HttpResponseRedirect(reverse('demos:bookmarks:bookmark') + '?id=' + str(bookmark.pk))


class BookmarkPermanentDeleteUI(View):
    """Only already soft-deleted, same-owner bookmarks can be purged."""
    def destination(self, request):
        fallback = reverse('demos:bookmarks:home') + '?deleted_only=1'
        value = request.POST.get('next') or request.GET.get('next') or fallback
        return value if url_has_allowed_host_and_scheme(value, {request.get_host()}, require_https=request.is_secure()) else fallback

    def get(self, request, bookmark_id):
        bookmark = get_object_or_404(Bookmark, owner=owner_for(request), pk=bookmark_id, status=-1)
        return render(request, ROOT + 'confirm_delete.html', {'bookmark': bookmark, 'next_url': self.destination(request)})

    def post(self, request, bookmark_id):
        if request.POST.get('confirm') != 'yes':
            return HttpResponseBadRequest('Explicit deletion confirmation is required.')
        try:
            with transaction.atomic():
                bookmark = get_object_or_404(Bookmark.objects.select_for_update(), owner=owner_for(request), pk=bookmark_id, status=-1)
                # Relationships use PROTECT: remove assignments before the bookmark.
                # Tags themselves are never deleted.
                BookmarkTag.objects.filter(bookmark=bookmark).delete()
                bookmark.delete()
        except ProtectedError:
            bookmark = get_object_or_404(Bookmark, owner=owner_for(request), pk=bookmark_id, status=-1)
            return render(request, ROOT + 'confirm_delete.html', {'bookmark': bookmark, 'next_url': self.destination(request), 'delete_error': 'This bookmark is referenced by other records and could not be removed. No changes were made.'}, status=409)
        messages.success(request, 'Bookmark permanently removed. Its URL can now be saved again.')
        return HttpResponseRedirect(self.destination(request))
