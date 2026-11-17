"""Derived workflow state, separate from user-managed subject tags."""
from django.db.models import Case, CharField, Value, When, Q, OuterRef, Subquery
from ..bookmark_ai_models import BookmarkEnrichmentAttempt

DOWNLOAD_STATES = (('not_requested', 'Not requested'), ('pending', 'Pending'), ('available', 'Available'),
                   ('unavailable', 'Content unavailable'), ('failed', 'Failed'))
ANALYSIS_STATES = (('not_requested', 'Not requested'), ('pending', 'Pending'), ('ready', 'Ready for review'),
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
    for mode, value, field in (('download', download, 'download_state'), ('analysis', analysis, 'analysis_state')):
        if not value:
            continue
        candidates = state_attempts(owner).filter(bookmark_id=OuterRef('pk'), url=OuterRef('url'))
        if mode == 'analysis':
            candidates = candidates.filter(mode='analyze')
        bookmarks = bookmarks.annotate(**{'_filter_' + mode: Subquery(candidates.order_by('-created_at', '-pk').values(field)[:1])})
        key = '_filter_' + mode
        bookmarks = bookmarks.filter(**{key + '__isnull': True}) if value == 'not_requested' else bookmarks.filter(**{key: value})
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
        bookmark.download_label = dict(DOWNLOAD_STATES)[bookmark.download_state]
        bookmark.analysis_label = dict(ANALYSIS_STATES)[bookmark.analysis_state]
        bookmark.download_attempt = attempt
        bookmark.analysis_attempt = analysis
        author = capture.retrieval.get('author') if capture else ''
        bookmark.article_author = author if isinstance(author, str) else ''
    return bookmarks
