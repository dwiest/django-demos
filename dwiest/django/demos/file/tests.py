import base64
import hashlib
import io
import json
import tempfile
import time
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch

import boto3
from moto import mock_aws
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.management import call_command, CommandError
from django.test import Client, TestCase, override_settings

from .storage import FileStore, StorageError
from .models import File

ROOT = '/apps/demos/file/'


@override_settings(FILE_MANAGER_BUCKET='file-manager-tests', FILE_MANAGER_TABLE='file-manager-tests',
                   FILE_MANAGER_REGION='us-east-1', ROOT_URLCONF='dwiest.django.demos.file.test_urls')
class FileManagerTests(TestCase):
    def setUp(self):
        self.aws = mock_aws()
        self.aws.start()
        self.addCleanup(self.aws.stop)
        dynamo = boto3.client('dynamodb', region_name='us-east-1')
        dynamo.create_table(TableName='file-manager-tests', BillingMode='PAY_PER_REQUEST',
            AttributeDefinitions=[{'AttributeName': name, 'AttributeType': 'S'} for name in ('pk', 'sk')],
            KeySchema=[{'AttributeName': 'pk', 'KeyType': 'HASH'}, {'AttributeName': 'sk', 'KeyType': 'RANGE'}])
        self.s3 = boto3.client('s3', region_name='us-east-1')
        self.s3.create_bucket(Bucket='file-manager-tests')
        self.s3.put_bucket_versioning(Bucket='file-manager-tests', VersioningConfiguration={'Status': 'Enabled'})
        self.user = get_user_model().objects.create_user(username='file-user', password='test')
        self.user.user_permissions.add(Permission.objects.get(content_type__app_label='demos', codename='access_file'))
        self.client.force_login(self.user)
        self.store = FileStore(self.user.pk)

    def register(self, key='upload-operation-0001', **changes):
        return self.store.register(dict({'original_name': 'sample.txt', 'size': 3, 'content_type': 'text/plain'}, **changes), key)

    def upload(self, registration, body=b'abc'):
        item = registration['file']
        return self.s3.put_object(Bucket=self.store.bucket, Key=item['object_key'], Body=body,
            ContentType='application/octet-stream', Metadata={'file-id': item['file_id']})

    def ready(self, **changes):
        registration = self.register(**changes)
        self.upload(registration)
        return self.store.complete(registration['file']['file_id'])

    def test_registration_is_idempotent_reserves_quota_and_signs_exact_size(self):
        first = self.register()
        again = self.register()
        self.assertEqual(first['file'], again['file'])
        self.assertEqual(self.store.summary()['files'], 1)
        self.assertEqual(self.store.summary()['size'], 3)
        policy = json.loads(base64.b64decode(first['upload']['fields']['policy']))
        self.assertIn(['content-length-range', 3, 3], policy['conditions'])
        self.assertIn({'Content-Type': 'application/octet-stream'}, policy['conditions'])
        with self.assertRaises(StorageError) as conflict:
            self.register(original_name='other.txt')
        self.assertEqual(conflict.exception.status, 409)
        self.assertFalse(File.objects.exists())

    @override_settings(FILE_MANAGER_MAX_FILES=1, FILE_MANAGER_MAX_TOTAL_FILESIZE=3)
    def test_quota_reservation_and_release_are_atomic_and_once(self):
        first = self.register()
        with self.assertRaises(StorageError):
            self.register(key='upload-operation-0002')
        self.assertEqual(self.store.summary()['files'], 1)
        self.store.delete(first['file']['file_id'])
        self.store.delete(first['file']['file_id'])
        self.assertEqual(self.store.summary()['files'], 0)
        self.assertEqual(self.store.summary()['size'], 0)
        self.register(key='upload-operation-0002')

    @override_settings(FILE_MANAGER_MAX_FILESIZE=3, FILE_MANAGER_MAX_TOTAL_FILESIZE=5)
    def test_byte_limits_and_unlimited_quotas(self):
        with self.assertRaises(StorageError):
            self.register(size=4)
        self.register()
        with self.assertRaises(StorageError):
            self.register(key='upload-operation-0002')
        self.assertEqual(self.store.summary()['size'], 3)
        self.store.table.put_item(Item={'pk': 'CONFIG', 'sk': 'QUOTA', 'max_files': 0,
                                       'max_filesize': 0, 'max_total_filesize': 0})
        self.register(key='upload-operation-0002', size=8)
        self.assertEqual(self.store.summary()['size'], 11)

    def test_listing_paginates_without_leaking_other_owners(self):
        with self.store.table.batch_writer() as batch:
            for i in range(102):
                file_id = format(i, '032x')
                batch.put_item(Item=dict(self.store.key(file_id), file_id=file_id, status='uploading'))
            batch.put_item(Item={'pk': 'USER#stranger', 'sk': 'FILE#' + 'f' * 32, 'status': 'ready'})
        first, cursor = self.store.listing()
        self.assertEqual(len(first), 100)
        second, next_cursor = self.store.listing(cursor)
        self.assertEqual(len(second), 2)
        self.assertIsNone(next_cursor)
        self.assertEqual(len({item['file_id'] for item in first + second}), 102)

    def test_completion_validates_upload_and_pins_version_across_replays(self):
        reg = self.register()
        fid = reg['file']['file_id']
        with self.assertRaises(StorageError):
            self.store.complete(fid)
        self.upload(reg, b'bad-size')
        with self.assertRaises(StorageError):
            self.store.complete(fid)
        original = self.upload(reg)
        saved = self.store.complete(fid)
        self.assertEqual(saved['version_id'], original['VersionId'])
        self.upload(reg, b'xyz')
        self.assertEqual(self.store.complete(fid)['version_id'], original['VersionId'])
        query = parse_qs(urlsplit(self.store.download(fid)).query)
        self.assertEqual(query['versionId'], [original['VersionId']])
        self.assertNotIn('upload', self.register())

    def test_expiry_and_versioning_configuration(self):
        reg = self.register()
        self.upload(reg)
        with patch('dwiest.django.demos.file.storage.time.time', return_value=time.time() + 4000):
            with self.assertRaises(StorageError) as expired:
                self.store.complete(reg['file']['file_id'])
            self.assertEqual(expired.exception.status, 410)
        self.s3.put_bucket_versioning(Bucket=self.store.bucket, VersioningConfiguration={'Status': 'Suspended'})
        self.upload(reg)
        with self.assertRaises(StorageError) as invalid:
            self.store.complete(reg['file']['file_id'])
        self.assertIn('versioning', str(invalid.exception))

    def test_all_operations_are_owner_scoped(self):
        item = self.ready()
        stranger = FileStore(self.user.pk + 1)
        for operation in (lambda: stranger.get(item['file_id']), lambda: stranger.complete(item['file_id']),
                          lambda: stranger.download(item['file_id']), lambda: stranger.delete(item['file_id']),
                          lambda: stranger.update(item['file_id'], 'stolen', '')):
            with self.assertRaises(StorageError) as missing:
                operation()
            self.assertEqual(missing.exception.status, 404)
        self.assertEqual(stranger.listing()[0], [])

    def test_auth_csrf_and_app_grants(self):
        self.client.logout()
        self.assertEqual(self.client.get(ROOT).status_code, 302)
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.assertEqual(client.post(ROOT + 'uploads/register/', '{}', content_type='application/json').status_code, 403)
        self.user.user_permissions.clear()
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(ROOT).status_code, 403)

    def test_views_upload_review_edit_download_delete(self):
        response = self.client.post(ROOT + 'uploads/register/', json.dumps({'original_name': '<script>.txt', 'size': 3}),
            content_type='application/json', HTTP_IDEMPOTENCY_KEY='browser-upload-00001')
        self.assertEqual(response.status_code, 200)
        fid = response.json()['file']['file_id']
        item = self.store.get(fid)
        self.assertContains(self.client.get(ROOT), '&lt;script&gt;.txt')
        url = ROOT + 'details/?path=' + fid
        self.assertContains(self.client.get(url), 'Verify upload')
        self.upload({'file': item})
        completed = self.client.post(ROOT + 'uploads/' + fid + '/complete/')
        self.assertEqual(completed.json()['detail_url'], url)
        self.assertContains(self.client.get(url), 'S3 versioning enabled')
        self.assertEqual(self.client.post(url, {'path': fid, 'name': 'renamed.txt', 'description': 'notes'}).status_code, 302)
        self.assertEqual(self.store.get(fid)['name'], 'renamed.txt')
        self.assertEqual(self.client.get(ROOT + 'download/?path=' + fid).status_code, 302)
        response = self.client.get(ROOT + 'delete/?path=' + fid)
        self.assertContains(response, 'Delete file?')
        self.assertEqual(self.store.get(fid)['status'], 'ready')
        self.assertEqual(self.client.post(ROOT + 'delete/', {'path': fid}).status_code, 302)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.post(ROOT).status_code, 405)

    def test_input_errors_cursor_and_dangerous_inline_type(self):
        self.assertEqual(self.client.post(ROOT + 'uploads/register/', '[]', content_type='application/json').status_code, 400)
        self.assertEqual(self.client.get(ROOT + '?cursor=bad').status_code, 400)
        self.assertEqual(self.client.get(ROOT + 'details/').status_code, 404)
        for size in (True, 0, 1073741825):
            with self.assertRaises(StorageError):
                self.register(size=size)
        item = self.ready(content_type='text/html')
        query = parse_qs(urlsplit(self.store.download(item['file_id'], inline=True)).query)
        self.assertTrue(query['response-content-disposition'][0].startswith('attachment'))
        self.assertEqual(query['response-content-type'], ['application/octet-stream'])

    def test_cleanup_releases_expired_reservations_and_purges_all_versions(self):
        reg = self.register()
        self.upload(reg)
        self.upload(reg)
        with patch('time.time', return_value=time.time() + 4000):
            call_command('cleanup_file_manager', stdout=io.StringIO())
            self.assertEqual(self.store.summary()['files'], 1)
            call_command('cleanup_file_manager', apply=True, stdout=io.StringIO())
            self.assertEqual(self.store.summary()['files'], 0)
            versions = self.s3.list_object_versions(Bucket=self.store.bucket)
            self.assertFalse(versions.get('Versions'))
            call_command('cleanup_file_manager', apply=True, stdout=io.StringIO())
            self.assertEqual(self.store.summary()['files'], 0)
            with self.assertRaises(StorageError):
                self.register()

    def test_migration_dry_run_resume_and_source_preservation(self):
        with tempfile.TemporaryDirectory() as folder:
            record = File.objects.create(owner=self.user, name='old.txt', content_type='text/plain', size=3,
                md5_checksum=hashlib.md5(b'abc').hexdigest(), sha256_checksum=hashlib.sha256(b'abc').hexdigest())
            source = Path(folder) / record.path
            source.write_bytes(b'abc')
            call_command('migrate_file_manager', source_dir=folder, stdout=io.StringIO())
            self.assertEqual(self.store.summary()['files'], 0)
            call_command('migrate_file_manager', source_dir=folder, apply=True, stdout=io.StringIO())
            self.assertEqual(self.store.get(record.path)['status'], 'ready')
            call_command('migrate_file_manager', source_dir=folder, apply=True, stdout=io.StringIO())
            self.assertEqual(self.store.summary()['files'], 1)
            self.assertTrue(source.exists())
            self.assertTrue(File.objects.filter(pk=record.pk).exists())
            source.write_bytes(b'wrong')
            with self.assertRaises(CommandError):
                call_command('migrate_file_manager', source_dir=folder, apply=True, stdout=io.StringIO())
