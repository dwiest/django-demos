"""Advance pending bookmark jobs once; run periodically independently of browsers."""
from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone
from ...bookmark_ai_models import BookmarkEnrichmentAttempt
from ...bookmarks.enrichment import TERMINAL, advance


class Command(BaseCommand):
    help = 'Advance pending retrieval/analysis jobs using their persisted idempotency keys.'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=100)

    def handle(self, *args, **options):
        if not 1 <= options['limit'] <= 1000:
            self.stderr.write('limit must be between 1 and 1000')
            return
        now = timezone.now()
        records = (BookmarkEnrichmentAttempt.objects.exclude(status__in=TERMINAL)
                   .filter(Q(retry_after__isnull=True) | Q(retry_after__lte=now))
                   .filter(Q(lease_until__isnull=True) | Q(lease_until__lte=now)).order_by('updated_at')[:options['limit']])
        for record in records:
            try:
                result = advance(record.pk)
                self.stdout.write('{} {}'.format(record.pk, result.status))
            except Exception:
                self.stderr.write('{} could not advance; it remains available for retry'.format(record.pk))
