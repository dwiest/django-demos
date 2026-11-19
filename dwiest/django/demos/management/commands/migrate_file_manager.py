"""Copy legacy SQL metadata/local files without deleting either source."""
import hashlib
import time
from pathlib import Path
from botocore.exceptions import BotoCoreError, ClientError

from django.core.management.base import BaseCommand, CommandError

from ...conf import settings
from ...file.models import File, FileQuota
from ...file.storage import FileStore, StorageError


class Command(BaseCommand):
    help = 'Copy local File Manager files and SQL metadata to S3/DynamoDB. Dry run unless --apply.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true')
        parser.add_argument('--source-dir', default=settings.DEMOS_FILE_UPLOAD_DIR)
        parser.add_argument('--anonymous-owner', type=int, help='Assign old unowned files to this existing Django user ID.')
        parser.add_argument('--copy-quota', action='store_true', help='Copy legacy quota row 1 to DynamoDB configuration.')

    def handle(self, *args, **options):
        from django.contrib.auth import get_user_model
        owner = options['anonymous_owner']
        if owner is not None and not get_user_model().objects.filter(pk=owner).exists():
            raise CommandError('anonymous-owner must identify an existing Django user.')
        if File.objects.filter(owner=None).exists() and owner is None:
            raise CommandError('Unowned legacy files exist. Supply --anonymous-owner USER_ID to assign them.')
        root = Path(options['source_dir']).resolve()
        # Preflight every source before starting any writes.
        records = []
        for record in File.objects.all().iterator():
            source = (root / record.path).resolve()
            if source.parent != root or not source.is_file():
                raise CommandError('Missing or invalid local source for file ID {}.'.format(record.pk))
            md5, sha = hashlib.md5(), hashlib.sha256()
            with source.open('rb') as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                    md5.update(chunk)
                    sha.update(chunk)
            if (source.stat().st_size != record.size or
                    (record.md5_checksum and md5.hexdigest() != record.md5_checksum) or
                    (record.sha256_checksum and sha.hexdigest() != record.sha256_checksum)):
                raise CommandError('Size or checksum mismatch for file ID {}.'.format(record.pk))
            records.append((record, source, md5.hexdigest(), sha.hexdigest()))
        self.stdout.write('{}: {} files checked.'.format('Apply' if options['apply'] else 'Dry run', len(records)))
        if not options['apply']:
            self.stdout.write('No changes made. Use --apply during a maintenance window after backing up SQL and uploads.')
            return
        try:
            if options['copy_quota']:
                quota = FileQuota.objects.filter(pk=1).values('max_files', 'max_filesize', 'max_total_filesize').first()
                if quota:
                    FileStore(owner or 0).table.put_item(Item=dict(quota, pk='CONFIG', sk='QUOTA'))
            for record, source, md5, sha in records:
                store = FileStore(record.owner_id if record.owner_id is not None else owner)
                key = store.key(record.path)
                previous = store.table.get_item(Key=key, ConsistentRead=True).get('Item')
                if previous:
                    if previous.get('legacy_id') != record.pk or previous.get('sha256_checksum') != sha:
                        raise CommandError('Destination conflicts with legacy file ID {}.'.format(record.pk))
                    if previous['status'] in ('ready', 'deleted'):
                        self.stdout.write('Already imported: {}'.format(record.pk))
                        continue
                else:
                    item = dict(key, file_id=record.path, legacy_id=record.pk, name=record.name,
                        original_name=record.name, size=record.size, content_type=record.content_type,
                        description=record.description or '', created_at=int(record.created_at.timestamp()),
                        legacy_versioned=record.versioned, legacy_downloadable=record.downloadable,
                        status='uploading', upload_until=int(time.time()) + 86400,
                        object_key='files/{}/{}'.format(store.owner[5:], record.path),
                        md5_checksum=md5, sha256_checksum=sha)
                    store.reserve(item, store.quota(), enforce=False)
                    previous = item
                # Refresh only the private import registration after a long interruption.
                store.table.update_item(Key=key, UpdateExpression='SET upload_until = :until',
                    ExpressionAttributeValues={':until': int(time.time()) + 86400})
                with source.open('rb') as stream:
                    store.s3.upload_fileobj(stream, store.bucket, previous['object_key'], ExtraArgs={
                        'ContentType': 'application/octet-stream', 'Metadata': {'file-id': record.path}})
                store.complete(record.path)
                self.stdout.write('Imported: {}'.format(record.pk))
        except StorageError as exc:
            raise CommandError(str(exc))
        except (BotoCoreError, ClientError):
            raise CommandError('AWS could not finish the import. Check role permissions/configuration and rerun to resume.') from None
        self.stdout.write('Import complete. Local files and SQL rows were retained. Re-run safely after an interruption.')
