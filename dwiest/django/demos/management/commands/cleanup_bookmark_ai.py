from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from ...bookmark_ai_models import BookmarkAIAnalysis


class Command(BaseCommand):
    help = 'Delete expired AI review records older than the retention period (default seven days).'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=7)

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(days=max(0, options['days']))
        count, _ = BookmarkAIAnalysis.objects.filter(expires_at__lt=cutoff).delete()
        self.stdout.write('Removed {} expired AI review records.'.format(count))
