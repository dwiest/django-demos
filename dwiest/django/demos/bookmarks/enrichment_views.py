from datetime import timedelta
from django.contrib import messages
from django.db import transaction
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, render, reverse
from django.utils import timezone

from ..bookmark_ai_models import BookmarkEnrichmentAttempt, BookmarkAIAnalysis
from .ai_credentials import AIError
from .ai_views import AIProtectedView, snapshot
from .enrichment import TERMINAL, advance, start, valid_proposal, review_sources
from .ui_views import ROOT


class EnrichmentView(AIProtectedView):
    def record(self, request, attempt_id):
        return get_object_or_404(BookmarkEnrichmentAttempt, pk=attempt_id, owner=request.user)

    def get(self, request, attempt_id):
        attempt = self.record(request, attempt_id)
        return render(request, ROOT + 'enrichment.html', {'attempt': attempt, 'active': attempt.status not in TERMINAL,
            'analysis_provenance': {k: v for k, v in attempt.analysis.items() if k != 'proposal'}})

    def post(self, request, attempt_id):
        attempt = self.record(request, attempt_id)
        action = request.POST.get('action')
        if action == 'advance':
            attempt = advance(attempt.pk)
            return JsonResponse({'status': attempt.status, 'message': attempt.error.get('message', ''),
                                 'terminal': attempt.status in TERMINAL})
        if action == 'review' and attempt.status == 'ready':
            with transaction.atomic():
                BookmarkEnrichmentAttempt.objects.filter(pk=attempt.pk, owner=request.user).update(updated_at=timezone.now())
                attempt.refresh_from_db()
                if not attempt.review_id:
                    review = BookmarkAIAnalysis.objects.create(owner=request.user, bookmark_id=attempt.bookmark_id,
                        original=attempt.original, proposal=valid_proposal(attempt.analysis, attempt.url),
                        sources=review_sources(attempt), expires_at=timezone.now() + timedelta(minutes=30))
                    attempt.review = review
                    attempt.save(update_fields=['review'])
                else:
                    BookmarkAIAnalysis.objects.filter(pk=attempt.review_id, owner=request.user, status='pending',
                        expires_at__lte=timezone.now()).update(expires_at=timezone.now() + timedelta(minutes=30))
            return HttpResponseRedirect(reverse('demos:bookmarks:ai_review', args=[attempt.review_id]))
        if action in ('retry_download', 'retry_analysis', 'analyze') and attempt.status in TERMINAL:
            if not attempt.bookmark or snapshot(attempt.bookmark) != attempt.original['persisted']:
                messages.error(request, 'The bookmark changed. Reopen its editor before starting another attempt.')
            else:
                try:
                    next_attempt = start(request.user, attempt.bookmark, attempt.original, attempt.url,
                        mode='analyze' if action in ('retry_analysis', 'analyze') else attempt.mode,
                        force_download=action == 'retry_download', force_analysis=action == 'retry_analysis',
                        retry_token=attempt.id.hex, source_attempt=attempt if action in ('retry_analysis', 'analyze') else None)
                    return HttpResponseRedirect(reverse('demos:bookmarks:enrichment', args=[next_attempt.pk]))
                except AIError as exc:
                    messages.error(request, str(exc))
        return HttpResponseRedirect(reverse('demos:bookmarks:enrichment', args=[attempt.pk]))
