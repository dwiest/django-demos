from datetime import timedelta
from django.contrib import messages
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, render, reverse
from django.utils import timezone

from ..bookmark_ai_models import BookmarkEnrichmentAttempt, BookmarkAIAnalysis
from .ai_credentials import AIError
from .ai_forms import AnalysisRetryForm
from .ai_views import AIProtectedView, snapshot
from .enrichment import TERMINAL, advance, start, valid_proposal, review_sources
from .ui_views import ROOT
from .record_views import provenance_rows, job_url


class EnrichmentView(AIProtectedView):
    def record(self, request, attempt_id):
        return get_object_or_404(BookmarkEnrichmentAttempt, pk=attempt_id, owner=request.user)

    def page(self, request, attempt, retry_form=None):
        return render(request, ROOT + 'enrichment.html', {'attempt': attempt, 'active': attempt.status not in TERMINAL,
            'retry_form': retry_form if retry_form is not None else AnalysisRetryForm(initial={'instructions': attempt.request_options.get('instructions', '')}),
            'used_instructions': attempt.request_options.get('instructions', ''),
            'proposal_applied': bool(attempt.review_id and attempt.review.status == 'applied'),
            'remote_status': (attempt.analysis if attempt.analysis_job_id else attempt.retrieval).get('job_status', ''),
            'provenance_rows': provenance_rows(attempt, {k: v for k, v in attempt.analysis.items() if k != 'proposal'}),
            'retrieval_rows': provenance_rows(attempt, attempt.retrieval),
            'can_retry_analysis': bool(attempt.retrieval_job_id and attempt.retrieval.get('retrieved') is True and attempt.mode == 'analyze')})

    def get(self, request, attempt_id):
        return self.page(request, self.record(request, attempt_id))

    def post(self, request, attempt_id):
        attempt = self.record(request, attempt_id)
        action = request.POST.get('action')
        if action == 'advance':
            attempt = advance(attempt.pk)
            now = timezone.now()
            wait_until = attempt.retry_after or attempt.lease_until
            wait = max(3, min(90, int((wait_until - now).total_seconds()) + 1)) if wait_until and wait_until > now else 3
            message = attempt.error.get('message', '')
            if attempt.lease_until and attempt.lease_until > now:
                message = message or 'Another progress check holds a lease until ' + attempt.lease_until.isoformat() + '.'
            return JsonResponse({'status': attempt.status, 'message': message,
                'terminal': attempt.status in TERMINAL, 'poll_after_seconds': wait,
                'retrieval_job_id': attempt.retrieval_job_id, 'analysis_job_id': attempt.analysis_job_id,
                'retrieval_url': job_url(attempt, 'retrieval') if attempt.retrieval_job_id else '',
                'analysis_url': job_url(attempt, 'analysis') if attempt.analysis_job_id else '',
                'remote_status': (attempt.analysis if attempt.analysis_job_id else attempt.retrieval).get('job_status', ''),
                'updated_at': attempt.updated_at.isoformat(),
                'lease_until': attempt.lease_until.isoformat() if attempt.lease_until else '',
                'retry_after': attempt.retry_after.isoformat() if attempt.retry_after else ''})
        if action == 'resume_analysis' and attempt.status == 'failed' and attempt.analysis_job_id:
            # Recheck an existing remote job after fixing local credentials/configuration.
            # This never creates a new remote job or repeats a provider call.
            BookmarkEnrichmentAttempt.objects.filter(pk=attempt.pk, owner=request.user, status='failed').filter(
                Q(lease_until__isnull=True) | Q(lease_until__lte=timezone.now())).update(
                    status='analyzing', error={}, retry_after=None, updated_at=timezone.now())
            return HttpResponseRedirect(reverse('demos:bookmarks:enrichment', args=[attempt.pk]))
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
            retry_form = AnalysisRetryForm({'instructions': request.POST.get('instructions', attempt.request_options.get('instructions', ''))})
            if not retry_form.is_valid():
                return self.page(request, attempt, retry_form)
            bookmark = attempt.bookmark
            if not bookmark or bookmark.url != attempt.url:
                messages.error(request, 'The bookmark URL changed or was deleted. Reopen its editor before starting another attempt.')
            else:
                current = snapshot(bookmark)
                original = attempt.original if current == attempt.original['persisted'] else {'persisted': current, 'draft': current}
                try:
                    next_attempt = start(request.user, bookmark, original, attempt.url,
                        mode='analyze' if action in ('retry_analysis', 'analyze') else attempt.mode,
                        force_download=action == 'retry_download', force_analysis=action == 'retry_analysis',
                        retry_token=attempt.id.hex, source_attempt=attempt if action in ('retry_analysis', 'analyze') else None,
                        instructions=retry_form.cleaned_data['instructions'])
                    return HttpResponseRedirect(reverse('demos:bookmarks:enrichment', args=[next_attempt.pk]))
                except AIError as exc:
                    messages.error(request, str(exc))
        return HttpResponseRedirect(reverse('demos:bookmarks:enrichment', args=[attempt.pk]))
