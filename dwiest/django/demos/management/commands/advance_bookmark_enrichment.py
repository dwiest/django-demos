"""Advance pending bookmark jobs once, or inspect persisted workflow state."""
import json
import uuid
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q
from django.utils import timezone
from ...bookmark_ai_models import BookmarkEnrichmentAttempt
from ...bookmarks.enrichment import TERMINAL, advance


class Command(BaseCommand):
    help = 'Advance pending retrieval/analysis jobs, or inspect a saved attempt without remote calls.'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=100)
        parser.add_argument('--attempt', help='Inspect or advance one attempt UUID.')
        parser.add_argument('--status-only', action='store_true', help='Print saved state without any AWS or job-service requests.')

    def report(self, record):
        self.stdout.write(json.dumps({
            'attempt': str(record.pk), 'status': record.status,
            'retrieval_job_id': record.retrieval_job_id, 'analysis_job_id': record.analysis_job_id,
            'remote_status': (record.analysis if record.analysis_job_id else record.retrieval).get('job_status'),
            'updated_at': record.updated_at, 'lease_until': record.lease_until,
            'retry_after': record.retry_after, 'error': record.error,
        }, default=str))

    def handle(self, *args, **options):
        if not 1 <= options['limit'] <= 1000:
            raise CommandError('limit must be between 1 and 1000')
        records = BookmarkEnrichmentAttempt.objects.all()
        if options['attempt']:
            try:
                attempt_id = uuid.UUID(options['attempt'])
            except ValueError:
                raise CommandError('attempt must be a UUID')
            records = records.filter(pk=attempt_id)
            if not records.exists():
                raise CommandError('Attempt not found')
        if options['status_only']:
            for record in records.order_by('-updated_at')[:options['limit']]:
                self.report(record)
            return
        now = timezone.now()
        due = (records.exclude(status__in=TERMINAL)
               .filter(Q(retry_after__isnull=True) | Q(retry_after__lte=now))
               .filter(Q(lease_until__isnull=True) | Q(lease_until__lte=now)))
        selected = list(due.order_by('updated_at')[:options['limit']])
        if not selected:
            self.stdout.write('No due attempts. Terminal records, active leases and future retry times are skipped.')
            if options['attempt']:
                self.report(records.get())
        for record in selected:
            try:
                self.report(advance(record.pk))
            except Exception:
                self.stderr.write('{} could not advance; inspect its saved state with --status-only'.format(record.pk))
