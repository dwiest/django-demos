from django.core.management.base import BaseCommand
from ...bookmarks.history import cleanup_failed


class Command(BaseCommand):
    help = 'Delete expired failed local workflow history using each account preference; preserve remote jobs and proposals.'

    def handle(self, *args, **options):
        self.stdout.write('Removed {} failed local attempts.'.format(cleanup_failed()))
