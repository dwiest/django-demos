"""Inspect or explicitly enable S3 bucket versioning; never suspend it."""
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from botocore.exceptions import BotoCoreError, ClientError
from ...media import s3_client


class Command(BaseCommand):
    help = 'Check S3 media bucket versioning; use --enable to enable version retention.'

    def add_arguments(self, parser):
        parser.add_argument('--enable', action='store_true')

    def handle(self, *args, **options):
        bucket = getattr(settings, 'STORE_MEDIA_BUCKET', 'rotten.world')
        try:
            client = s3_client()
            status = client.get_bucket_versioning(Bucket=bucket).get('Status', 'Disabled')
            if options['enable'] and status != 'Enabled':
                client.put_bucket_versioning(Bucket=bucket, VersioningConfiguration={'Status': 'Enabled'})
                status = client.get_bucket_versioning(Bucket=bucket).get('Status', 'Disabled')
                if status != 'Enabled':
                    raise CommandError('S3 did not confirm that versioning is enabled.')
            self.stdout.write('{}: versioning {}'.format(bucket, status))
        except (BotoCoreError, ClientError) as error:
            raise CommandError('Could not configure bucket versioning: {}'.format(error))
