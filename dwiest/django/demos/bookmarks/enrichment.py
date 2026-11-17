"""Durable, leased retrieval -> analysis -> review orchestration, independent of browsers."""
import hashlib
import json
import uuid
import re
from datetime import date
from datetime import timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from ..bookmark_ai_models import BookmarkAISettings, BookmarkAIAnalysis, BookmarkEnrichmentAttempt, BookmarkAIAttempt
from .ai_credentials import AIError, require_demo_owner
from .job_client import JobClient, JobError, connection
from .models import Bookmark, Tag

TERMINAL = ('ready', 'downloaded', 'failed', 'cancelled')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def start(owner, bookmark, original, url, mode='analyze', force_download=False, force_analysis=False, retry_token=None, source_attempt=None):
    require_demo_owner(owner)
    if bookmark.owner_id != owner.pk:
        raise AIError('Only your own bookmarks can be enriched.')
    if not bookmark.pk:
        raise AIError('Save the bookmark first, then retrieve or analyze its URL. Automatic enrichment on creation is a separate update.')
    base, _ = connection()
    prefs, _ = BookmarkAISettings.objects.get_or_create(owner=owner)
    tags = list(Tag.objects.filter(owner=owner).order_by('title', 'id').values_list('title', flat=True))
    options = {'include_raw_html': prefs.include_raw_html, 'force_refresh': force_download,
               'existing_tags': [name for name in tags if len(name) <= 80][:200],
               'analysis_nonce': (retry_token or uuid.uuid4().hex) if force_analysis else ''}
    source = {}
    if source_attempt is not None:
        if (source_attempt.owner_id != owner.pk or source_attempt.bookmark_id != bookmark.pk
                or source_attempt.service_url != base or source_attempt.url != url
                or source_attempt.retrieval.get('retrieved') is not True):
            raise AIError('A readable capture from this bookmark and service is required.')
        source = {'retrieval_job_id': valid_job_id(source_attempt.retrieval_job_id),
                  'retrieval': source_attempt.retrieval, 'status': 'analysis_pending'}
        options['include_raw_html'] = source_attempt.request_options['include_raw_html']
    fingerprint = digest({'capture': source.get('retrieval_job_id'), 'bookmark': bookmark.pk, 'url': url, 'service': base, 'mode': mode,
                          'original': original, 'options': options,
                          'refresh_nonce': (retry_token or uuid.uuid4().hex) if force_download else ''})
    attempt, _ = BookmarkEnrichmentAttempt.objects.get_or_create(owner=owner, fingerprint=fingerprint,
        defaults={'bookmark_id': bookmark.pk, 'url': url, 'service_url': base, 'mode': mode, 'original': original, 'request_options': options, **source})
    BookmarkAIAttempt.objects.update_or_create(owner=owner, url=url, defaults={})
    return attempt


def valid_job_id(value):
    if not isinstance(value, str) or not re.fullmatch(r'[a-f0-9]{32}', value):
        raise AIError('The job service returned an invalid job reference.')
    return value


def valid_proposal(result, url):
    proposal = dict(result['proposal'], url=url)
    if (set(proposal) != {'url', 'title', 'description', 'article_date', 'tags'}
            or not isinstance(proposal['title'], str) or len(proposal['title']) > 2000
            or not isinstance(proposal['description'], str) or len(proposal['description']) > 20000
            or not isinstance(proposal['tags'], list) or len(proposal['tags']) > 30
            or any(not isinstance(name, str) or len(name) > 255 for name in proposal['tags'])):
        raise AIError('The analysis returned an invalid bookmark proposal.')
    if proposal['article_date'] is not None:
        if not isinstance(proposal['article_date'], str) or len(proposal['article_date']) != 10:
            raise AIError('The analysis returned an invalid publication date.')
        date.fromisoformat(proposal['article_date'])
    return proposal


def review_sources(attempt):
    from .ai_forms import AnalyzeForm
    candidate = attempt.retrieval.get('final_url') or attempt.url
    form = AnalyzeForm({'url': candidate})
    url = form.cleaned_data['url'] if form.is_valid() else attempt.url
    return [{'url': url, 'title': 'Saved capture ' + attempt.retrieval_job_id,
             'capture_id': attempt.retrieval_job_id, 'analysis_id': attempt.analysis_job_id}]


def fail(attempt, message, details=None):
    attempt.status = 'failed'
    attempt.error = dict(details or {})
    # Keep the service's actionable message instead of replacing it with a generic one.
    attempt.error['message'] = attempt.error.get('message') or message


def advance(attempt_id):
    stamp = timezone.now()
    token = uuid.uuid4().hex
    claimed = (BookmarkEnrichmentAttempt.objects.filter(pk=attempt_id).exclude(status__in=TERMINAL)
               .filter(Q(lease_until__isnull=True) | Q(lease_until__lte=stamp))
               .filter(Q(retry_after__isnull=True) | Q(retry_after__lte=stamp))
               .update(lease_token=token, lease_until=stamp + timedelta(seconds=90)))
    if not claimed:
        return BookmarkEnrichmentAttempt.objects.get(pk=attempt_id)
    attempt = BookmarkEnrichmentAttempt.objects.select_related('owner').get(pk=attempt_id)
    try:
        require_demo_owner(attempt.owner)
        if not attempt.bookmark:
            raise AIError('The bookmark was deleted. This attempt cannot apply changes.')
        client = JobClient(attempt.owner, attempt.service_url)
        if attempt.status == 'retrieval_pending':
            payload = {'type': 'web.retrieve', 'version': 1, 'request': {'url': attempt.url,
                'include_raw_html': attempt.request_options['include_raw_html']}, 'client_reference': 'bookmark:' + str(attempt.bookmark_id)}
            if attempt.request_options['force_refresh']:
                payload['request']['force_refresh'] = True
            job = client.submit(payload, 'bookmark-retrieval:' + attempt.id.hex)
            attempt.retrieval_job_id = valid_job_id(job['job_id'])
            attempt.retrieval = {'reused': job.get('reused', False)}
            attempt.status = 'retrieving'
        elif attempt.status == 'retrieving':
            job = client.job(attempt.retrieval_job_id)
            attempt.retrieval['job_status'] = job['status']
            if job['status'] == 'failed':
                fail(attempt, 'Retrieval worker failed.', job.get('error'))
            elif job['status'] == 'completed':
                result = client.job(attempt.retrieval_job_id, result=True)['result']
                attempt.retrieval.update({k: v for k, v in result.items() if k != 'text'})
                if result.get('retrieved') is not True:
                    fail(attempt, result.get('failure_message') or 'Page content is unavailable.', attempt.retrieval)
                else:
                    attempt.status = 'downloaded' if attempt.mode == 'download' else 'analysis_pending'
        elif attempt.status == 'analysis_pending':
            payload = {'type': 'ai.analyze', 'version': 1, 'request': {'capture_id': attempt.retrieval_job_id,
                'configuration': 'bookmark.enrichment.v1', 'existing_tags': attempt.request_options['existing_tags']}}
            key = 'bookmark-analysis:' + digest({'request': payload, 'nonce': attempt.request_options['analysis_nonce']})
            job = client.submit(payload, key)
            attempt.analysis_job_id = valid_job_id(job['job_id'])
            attempt.status = 'analyzing'
        elif attempt.status == 'analyzing':
            job = client.job(attempt.analysis_job_id)
            attempt.analysis['job_status'] = job['status']
            if job['status'] == 'failed':
                fail(attempt, 'Analysis did not complete. Use Retry analysis to request another provider call.', job.get('error'))
            elif job['status'] == 'completed':
                result = client.job(attempt.analysis_job_id, result=True)['result']
                proposal = valid_proposal(result, attempt.url)
                attempt.analysis = result
                with transaction.atomic():
                    # Claim is held until this transaction commits. Recoverable work never auto-applies.
                    if not BookmarkEnrichmentAttempt.objects.filter(pk=attempt.pk, lease_token=token).update(updated_at=timezone.now()):
                        raise AIError('Another worker advanced this attempt.')
                    current = BookmarkEnrichmentAttempt.objects.get(pk=attempt.pk)
                    if current.lease_token != token:
                        raise AIError('Another worker advanced this attempt.')
                    if not current.review_id:
                        review = BookmarkAIAnalysis.objects.create(owner=attempt.owner, bookmark_id=attempt.bookmark_id,
                            original=attempt.original, proposal=proposal,
                            sources=review_sources(attempt),
                            expires_at=timezone.now() + timedelta(minutes=30))
                        attempt.review_id = review.pk
                        BookmarkEnrichmentAttempt.objects.filter(pk=attempt.pk, lease_token=token).update(review=review)
                    else:
                        attempt.review_id = current.review_id
                attempt.status = 'ready'
        attempt.error = attempt.error if attempt.status == 'failed' else {}
        attempt.retry_after = None
    except JobError as exc:
        if exc.transient:
            attempt.error = dict(exc.details, message=str(exc))
            attempt.retry_after = timezone.now() + timedelta(seconds=30)
        else:
            fail(attempt, str(exc), exc.details)
    except AIError as exc:
        fail(attempt, str(exc), exc.details)
    except (KeyError, TypeError, ValueError):
        fail(attempt, 'The job service returned an invalid operation response.')
    finally:
        BookmarkEnrichmentAttempt.objects.filter(pk=attempt.pk, lease_token=token).update(
            status=attempt.status, retrieval_job_id=attempt.retrieval_job_id, analysis_job_id=attempt.analysis_job_id,
            retrieval=attempt.retrieval, analysis=attempt.analysis, review_id=attempt.review_id, error=attempt.error,
            retry_after=attempt.retry_after, updated_at=timezone.now(), lease_token='', lease_until=None)
    return BookmarkEnrichmentAttempt.objects.get(pk=attempt.pk)
