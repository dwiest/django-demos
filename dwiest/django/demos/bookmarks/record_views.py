"""Read-only, owner-bound access to the same service records used by reconciliation.

Browser Cognito IDs and application user references are deliberately separate.
Never accept a remote job ID, endpoint or artifact URL supplied by the browser.
"""
from urllib.parse import urlsplit
from django.http import Http404
from django.shortcuts import get_object_or_404, render, reverse
from .ai_views import AIProtectedView
from .ai_credentials import AIError
from .job_client import JobClient
from .ui_views import ROOT
from ..bookmark_ai_models import BookmarkEnrichmentAttempt


def job_url(attempt, kind):
    return reverse('demos:bookmarks:job_record', args=[attempt.pk, kind])


def provenance_rows(attempt, values):
    rows = []
    for key, value in values.items():
        link = ''
        if key in ('analysis_id', 'provider_response_id') and attempt.analysis_job_id:
            link = job_url(attempt, 'analysis') + ('#provider_response_id' if key == 'provider_response_id' else '')
        elif key == 'capture_id' and attempt.retrieval_job_id:
            link = job_url(attempt, 'retrieval')
        elif key in ('configuration', 'model_requested', 'model', 'prompt_version'):
            link = reverse('demos:bookmarks:ai_settings') + '#service-analysis-settings'
        rows.append({'key': key, 'value': value, 'link': link, 'json': isinstance(value, (dict, list))})
    return rows


class AttemptRecordView(AIProtectedView):
    def get(self, request, attempt_id):
        attempt = get_object_or_404(BookmarkEnrichmentAttempt, pk=attempt_id, owner=request.user)
        record = {name: getattr(attempt, name) for name in (
            'id', 'bookmark_id', 'url', 'status', 'mode', 'created_at', 'updated_at',
            'retrieval_job_id', 'analysis_job_id', 'request_options', 'retrieval', 'analysis', 'error')}
        return render(request, ROOT + 'job_record.html', {'attempt': attempt, 'heading': 'Saved workflow attempt', 'record': record})


class JobRecordView(AIProtectedView):
    def get(self, request, attempt_id, kind):
        attempt = get_object_or_404(BookmarkEnrichmentAttempt, pk=attempt_id, owner=request.user)
        if kind not in ('retrieval', 'analysis'):
            raise Http404('Job not found')
        job_id = getattr(attempt, kind + '_job_id')
        if not job_id:
            raise Http404('Job has not been submitted')
        context = {'attempt': attempt, 'heading': ('Download' if kind == 'retrieval' else 'AI analysis') + ' job',
                   'kind': kind, 'job_id': job_id, 'record': {}, 'result': None, 'downloads': []}
        try:
            client = JobClient(request.user, attempt.service_url)
            context['record'] = client.job(job_id)
            if context['record'].get('status') == 'completed':
                saved = client.job(job_id, result=True)
                context['result'] = saved.get('result')
                if isinstance(context['result'], dict):
                    context['rows'] = provenance_rows(attempt, {k: v for k, v in context['result'].items() if k != 'text'})
                    context['article_text'] = context['result'].get('text', '')
                for name, url in saved.get('downloads', {}).items():
                    parsed = urlsplit(url)
                    if parsed.scheme == 'https' and parsed.hostname and not parsed.username and not parsed.password:
                        context['downloads'].append({'name': name, 'url': url})
        except AIError as exc:
            context['record_error'] = str(exc)
        return render(request, ROOT + 'job_record.html', context)
