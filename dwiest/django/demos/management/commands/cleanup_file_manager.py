"""Expire abandoned upload reservations and purge deleted object versions."""
import time
from botocore.exceptions import BotoCoreError, ClientError
from django.core.management.base import BaseCommand, CommandError
from ...file.storage import FileStore, StorageError


class Command(BaseCommand):
    help = 'Release expired upload reservations and purge deleted files. Run hourly. Dry run unless --apply.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true')

    def handle(self, *args, **options):
        try:
            store = FileStore(0)
            args = {'ConsistentRead': True}
            count = 0
            while True:
                page = store.table.scan(**args)
                for item in page.get('Items', []):
                    if not item['sk'].startswith('FILE#') or item.get('purged'):
                        continue
                    expired = item['status'] == 'uploading' and item['upload_until'] < time.time()
                    if item['status'] != 'deleted' and not expired:
                        continue
                    count += 1
                    if options['apply']:
                        owner_store = FileStore(item['pk'][5:])
                        if expired:
                            owner_store.delete(item['file_id'])
                            item = owner_store.get(item['file_id'], include_deleted=True)
                        owner_store.purge(item)
                if not page.get('LastEvaluatedKey'):
                    break
                args['ExclusiveStartKey'] = page['LastEvaluatedKey']
            self.stdout.write('{}: {} entries processed.'.format('Apply' if options['apply'] else 'Dry run', count))
        except StorageError as exc:
            raise CommandError(str(exc))
        except (BotoCoreError, ClientError):
            raise CommandError('AWS could not finish cleanup. Check role permissions/configuration and rerun.') from None
