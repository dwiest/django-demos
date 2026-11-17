"""Local workflow history only: deletion never calls a remote API or deletes proposals."""
from datetime import timedelta
from django.db.models import Q
from django.utils import timezone
from ..bookmark_ai_models import BookmarkAISettings, BookmarkEnrichmentAttempt

REMOVABLE = ('failed', 'downloaded', 'applied', 'cancelled')


def removable(query):
    return query.filter(status__in=REMOVABLE).filter(
        Q(lease_until__isnull=True) | Q(lease_until__lte=timezone.now())).exclude(review__status='pending')


def cleanup_failed(owner=None, days=None):
    prefs = BookmarkAISettings.objects.all()
    if owner is not None:
        prefs = prefs.filter(owner=owner)
    removed = 0
    for setting in prefs.iterator():
        retention = setting.failed_attempt_retention_days if days is None else days
        if retention is None:
            continue
        rows = removable(BookmarkEnrichmentAttempt.objects.filter(owner=setting.owner, status='failed',
            updated_at__lt=timezone.now() - timedelta(days=retention)))
        count, _ = rows.delete()
        removed += count
    return removed


def outcome_label(attempt):
    if attempt.status != 'failed':
        return 'Applied automatically' if attempt.status == 'applied' else attempt.status.replace('_', ' ').capitalize()
    code = attempt.error.get('code', '')
    if code in ('workflow_timeout', 'job_deadline_exceeded'):
        return 'Timed out'
    if attempt.error.get('http_status') and not code:
        return 'Submission or access failure'
    return 'Job failed' if code else 'Workflow failed'
