"""Derived workflow state, separate from user-managed subject tags."""
from django.db.models import Case, CharField, Value, When, Q, OuterRef, Subquery
from django.db.models.functions import Coalesce
from ..bookmark_ai_models import BookmarkEnrichmentAttempt

DOWNLOAD_STATES = (('not_requested', 'Not requested'), ('pending', 'Pending'), ('available', 'Available'),
                   ('unavailable', 'Content unavailable'), ('failed', 'Failed'))
ANALYSIS_STATES = (('not_available', 'Not available'), ('not_requested', 'Not requested'), ('pending', 'Pending'), ('ready', 'Ready for review'),
                   ('applied', 'Applied'), ('failed', 'Failed'), ('cancelled', 'Cancelled'))


def state_attempts(owner):
    return BookmarkEnrichmentAttempt.objects.filter(owner=owner).annotate(
        download_state=Case(
            When(retrieval__retrieved=True, then=Value('available')),
            When(retrieval__retrieved=False, then=Value('unavailable')),
            When(status='failed', then=Value('failed')),
            When(status='cancelled', then=Value('failed')),
            default=Value('pending'), output_field=CharField()),
        analysis_state=Case(
            When(mode='download', then=Value('not_requested')),
            When(status__in=('ready', 'applied', 'failed', 'cancelled'), then='status'),
            default=Value('pending'), output_field=CharField()))


def filter_state(bookmarks, owner, download='', analysis=''):
    if not download and not analysis:
        return bookmarks
    candidates = state_attempts(owner).filter(bookmark_id=OuterRef('pk'), url=OuterRef('url')).order_by('-created_at', '-pk')
    analyses = candidates.filter(mode='analyze')
    bookmarks = bookmarks.annotate(
        _filter_download=Coalesce(Subquery(candidates.values('download_state')[:1]), Value('not_requested')),
        _analysis_raw=Coalesce(Subquery(analyses.values('analysis_state')[:1]), Value('not_requested')),
        _analysis_job=Coalesce(Subquery(analyses.values('analysis_job_id')[:1]), Value('')))
    bookmarks = bookmarks.annotate(_filter_analysis=Case(
        When(Q(_filter_download__in=('failed', 'unavailable')) & Q(_analysis_job='') &
             Q(_analysis_raw__in=('not_requested', 'failed')), then=Value('not_available')),
        default='_analysis_raw', output_field=CharField()))
    if download:
        bookmarks = bookmarks.filter(_filter_download=download)
    if analysis:
        bookmarks = bookmarks.filter(_filter_analysis=analysis)
    return bookmarks


def decorate(bookmarks, owner):
    bookmarks = list(bookmarks)
    newest = BookmarkEnrichmentAttempt.objects.filter(owner=owner, bookmark_id=OuterRef('bookmark_id'), url=OuterRef('url')).order_by('-created_at', '-pk')
    latest_analysis = newest.filter(mode='analyze')
    latest_capture = newest.filter(retrieval__retrieved=True)
    found, analyses, captures = {}, {}, {}
    # Three bounded queries, independent of bookmark count and history length.
    current = Q(pk__isnull=True)
    for bookmark in bookmarks:
        current |= Q(bookmark_id=bookmark.pk, url=bookmark.url)
    for target, candidates in ((found, newest), (analyses, latest_analysis), (captures, latest_capture)):
        for attempt in state_attempts(owner).filter(current, pk=Subquery(candidates.values('pk')[:1])):
            target[(attempt.bookmark_id, attempt.url)] = attempt
    for bookmark in bookmarks:
        key = (bookmark.pk, bookmark.url)
        attempt, analysis, capture = found.get(key), analyses.get(key), captures.get(key)
        bookmark.download_state = attempt.download_state if attempt else 'not_requested'
        bookmark.analysis_state = analysis.analysis_state if analysis else 'not_requested'
        if (bookmark.download_state in ('failed', 'unavailable') and
                (not analysis or not analysis.analysis_job_id) and bookmark.analysis_state in ('not_requested', 'failed')):
            bookmark.analysis_state = 'not_available'
        bookmark.download_label = dict(DOWNLOAD_STATES)[bookmark.download_state]
        bookmark.analysis_label = dict(ANALYSIS_STATES)[bookmark.analysis_state]
        bookmark.download_attempt = attempt
        bookmark.analysis_attempt = analysis or (attempt if bookmark.analysis_state == 'not_available' else None)
        author = capture.retrieval.get('author') if capture else ''
        bookmark.article_author = author if isinstance(author, str) else ''
    return bookmarks
