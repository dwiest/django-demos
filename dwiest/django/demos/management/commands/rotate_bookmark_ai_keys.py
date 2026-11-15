from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.views.decorators.debug import sensitive_variables
from ...bookmarks.ai_credentials import AIError, cipher
from ...bookmark_ai_models import BookmarkAISettings


class Command(BaseCommand):
    help = 'Re-encrypt saved OpenAI keys with the first configured AI encryption key. Keep old keys until all sessions expire.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')

    @sensitive_variables()
    def handle(self, *args, **options):
        try:
            encryption = cipher()
            count = 0
            with transaction.atomic():
                for row in BookmarkAISettings.objects.select_for_update().exclude(encrypted_api_key='').iterator():
                    rotated = encryption.rotate(row.encrypted_api_key.encode('ascii')).decode('ascii')
                    if not options['dry_run']:
                        row.encrypted_api_key = rotated
                        row.save(update_fields=['encrypted_api_key'])
                    count += 1
        except AIError as exc:
            raise CommandError(str(exc)) from None
        except Exception:
            raise CommandError('Rotation failed. No saved keys were changed. Check that all required old keys are configured.') from None
        self.stdout.write('{} {} saved credentials.'.format('Validated' if options['dry_run'] else 'Rotated', count))
