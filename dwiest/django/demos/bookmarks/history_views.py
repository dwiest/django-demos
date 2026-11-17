import uuid
from django.contrib import messages
from django.core import signing
from django.core.paginator import Paginator
from django.http import HttpResponseRedirect
from django.shortcuts import render, reverse
from ..bookmark_ai_models import BookmarkEnrichmentAttempt
from .ai_views import AIProtectedView
from .history import removable, outcome_label
from .ui_views import ROOT

SALT = 'bookmark-history-cleanup-v1'


class EnrichmentHistoryView(AIProtectedView):
    def records(self, request):
        query = BookmarkEnrichmentAttempt.objects.filter(owner=request.user)
        value = request.GET.get('bookmark')
        if value:
            try:
                query = query.filter(bookmark_id=int(value))
            except ValueError:
                query = query.none()
        return query

    def page(self, request, confirmation=None):
        page = Paginator(self.records(request).order_by('-created_at'), 25).get_page(request.GET.get('page'))
        allowed = set(removable(BookmarkEnrichmentAttempt.objects.filter(owner=request.user, pk__in=[row.pk for row in page])).values_list('pk', flat=True))
        for attempt in page:
            attempt.outcome_label = outcome_label(attempt)
            attempt.can_remove = attempt.pk in allowed
        return render(request, ROOT + 'enrichment_history.html', {'nav_section': 'history', 'page_obj': page,
            'bookmark_filter': request.GET.get('bookmark', ''), 'confirmation': confirmation})

    def get(self, request):
        return self.page(request)

    def post(self, request):
        action = request.POST.get('action')
        if action in ('preview_failed', 'preview_remove'):
            query = removable(self.records(request))
            if action == 'preview_failed':
                query = query.filter(status='failed')
            else:
                try:
                    query = query.filter(pk=uuid.UUID(request.POST.get('attempt', '')))
                except (ValueError, TypeError, AttributeError):
                    query = query.none()
            # Preview a bounded immutable set; later failures are never silently included.
            items = [(str(row.pk), row.status, row.updated_at.isoformat()) for row in query[:100]]
            token = signing.dumps({'owner': request.user.pk, 'items': items}, salt=SALT, compress=True)
            return self.page(request, {'token': token, 'count': len(items)})
        if action == 'confirm':
            try:
                preview = signing.loads(request.POST.get('token', ''), salt=SALT, max_age=900)
                if preview['owner'] != request.user.pk:
                    raise signing.BadSignature()
                from django.db.models import Q
                matches = Q(pk__in=[])
                for pk, status, updated_at in preview['items']:
                    matches |= Q(pk=pk, status=status, updated_at=updated_at)
                count, _ = removable(BookmarkEnrichmentAttempt.objects.filter(owner=request.user).filter(matches)).delete()
            except (signing.BadSignature, KeyError, ValueError):
                messages.error(request, 'Cleanup preview expired or is invalid. Preview again.')
            else:
                messages.success(request, 'Removed {} local attempts. Remote jobs and proposals were preserved.'.format(count))
        return HttpResponseRedirect(reverse('demos:bookmarks:enrichment_history'))
