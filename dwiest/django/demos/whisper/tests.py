import json
from unittest.mock import patch, MagicMock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import Client, TestCase, override_settings
from botocore.credentials import Credentials

from .client import WhisperClient, ServiceError

FILE_ID = 'a' * 32
ROOT = '/apps/demos/whisper/'
FILE = {'file_id': FILE_ID, 'display_name': 'Meeting', 'original_name': 'meeting.mp3', 'size': 3,
        'content_type': 'audio/mpeg', 'status': 'ready', 'created_at': 1800000000, 'ready_at': 1800000001,
        'updated_at': 1800000001, 'retention_days': None, 'expires_at': None}


class WhisperViewsTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='whisper-user', password='test')
        self.permission = Permission.objects.get(content_type__app_label='demos', codename='access_whisper')
        self.user.user_permissions.add(self.permission)
        self.client.force_login(self.user)
        self.mock = patch('dwiest.django.demos.whisper.views.WhisperClient').start()
        self.addCleanup(patch.stopall)
        self.service = self.mock.return_value

    def test_application_migration_and_grants(self):
        from ..application_models import Application
        self.assertTrue(Application.objects.get(key='whisper').enabled)
        self.user.user_permissions.clear()
        self.assertEqual(self.client.get(ROOT).status_code, 403)
        self.mock.assert_not_called()

    def test_anonymous_and_csrf(self):
        self.client.logout()
        self.assertEqual(self.client.get(ROOT).status_code, 302)
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.assertEqual(client.post(ROOT + 'uploads/register/', '{}', content_type='application/json').status_code, 403)
        self.assertEqual(client.post(ROOT + 'files/' + FILE_ID + '/delete/').status_code, 403)

    def test_library_and_upload_screen(self):
        self.service.request.return_value = {'files': [dict(FILE, display_name='<script>bad()</script>')], 'next_cursor': None}
        response = self.client.get(ROOT)
        self.assertContains(response, '&lt;script&gt;bad()&lt;/script&gt;')
        self.assertNotContains(response, '<script>bad()</script>')
        self.mock.assert_called_with(self.user)
        self.assertContains(self.client.get('/apps/demos/'), 'Open Whisper')
        response = self.client.get(ROOT + 'upload/')
        self.assertContains(response, 'media-upload')
        self.assertContains(response, 'csrfmiddlewaretoken')
        self.assertNotContains(response, 'name="api_key"')

    def test_registration_forwards_identity_and_reuses_operation_key(self):
        self.service.request.return_value = {'file': FILE, 'upload': {'url': 'https://storage.example.test/', 'fields': {}}}
        payload = {'original_name': 'meeting.mp3', 'size': 3}
        response = self.client.post(ROOT + 'uploads/register/', json.dumps(payload), content_type='application/json', HTTP_IDEMPOTENCY_KEY='operation-1')
        self.assertEqual(response.status_code, 200)
        self.service.request.assert_called_with('POST', '/files', payload, 'operation-1')
        self.assertEqual(response.json()['detail_url'], ROOT + 'files/' + FILE_ID + '/')
        self.assertEqual(self.client.get(ROOT + 'uploads/register/').status_code, 405)
        self.assertEqual(self.client.post(ROOT + 'uploads/register/', '[]', content_type='application/json').status_code, 400)

    def test_completion_and_resume(self):
        self.service.request.return_value = {'file': FILE}
        url = ROOT + 'files/' + FILE_ID + '/complete/'
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertEqual(self.client.post(url).status_code, 200)
        self.service.request.assert_called_with('POST', '/files/' + FILE_ID + '/complete', {})
        self.service.request.return_value = {'file': dict(FILE, status='uploading')}
        response = self.client.get(ROOT + 'files/' + FILE_ID + '/')
        self.assertContains(response, 'Verify upload')

    def test_edit_and_retention(self):
        self.service.request.return_value = {'file': FILE}
        url = ROOT + 'files/' + FILE_ID + '/'
        response = self.client.post(url, {'display_name': 'New name', 'keep_indefinitely': 'on'})
        self.assertEqual(response.status_code, 302)
        self.service.request.assert_called_with('POST', '/files/' + FILE_ID, {'display_name': 'New name', 'retention_days': None})
        response = self.client.post(url, {'display_name': 'Name', 'retention_days': '0'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Ensure this value is greater than or equal to 1')

    def test_missing_other_owner_and_service_errors(self):
        self.service.request.side_effect = ServiceError('File not found.', 404)
        self.assertEqual(self.client.get(ROOT + 'files/' + FILE_ID + '/').status_code, 404)
        self.mock.side_effect = ServiceError('Configure the service.')
        self.assertContains(self.client.get(ROOT), 'Configure the service.', status_code=503)

    def test_delete_requires_post_and_download_is_private(self):
        self.service.request.return_value = {'file': FILE}
        url = ROOT + 'files/' + FILE_ID + '/delete/'
        self.assertContains(self.client.get(url), 'Delete file?')
        self.assertEqual(self.service.request.call_count, 1)  # GET only reads the record.
        self.assertEqual(self.client.post(url).status_code, 302)
        self.service.request.assert_called_with('DELETE', '/files/' + FILE_ID)
        self.service.request.return_value = {'url': 'https://storage.example.test/signed'}
        response = self.client.get(ROOT + 'files/' + FILE_ID + '/download/')
        self.assertEqual(response.url, 'https://storage.example.test/signed')
        self.assertIn('no-store', response['Cache-Control'])
        self.service.request.return_value = {'url': 'http://storage.example.test/unsafe'}
        self.assertEqual(self.client.get(ROOT + 'files/' + FILE_ID + '/download/').status_code, 503)

    @override_settings(WHISPER_SERVICE_URL='https://media.example.test/service', WHISPER_SERVICE_REGION='us-east-1')
    def test_signed_client_uses_server_identity_and_refuses_redirects(self):
        client = WhisperClient(self.user)
        self.assertEqual(client.user_reference, str(self.user.pk))
        with patch('dwiest.django.demos.whisper.client.boto3.Session') as session, patch('dwiest.django.demos.whisper.client.build_opener') as opener:
            session.return_value.get_credentials.return_value = Credentials('test-id', 'test-secret')
            opener.return_value.open.return_value.__enter__.return_value.read.return_value = b'{"files": []}'
            self.assertEqual(client.request('GET', '/files'), {'files': []})
            request = opener.return_value.open.call_args[0][0]
            self.assertEqual(request.get_header('X-user-reference'), str(self.user.pk))
            self.assertIn('AWS4-HMAC-SHA256', request.get_header('Authorization'))
        with override_settings(WHISPER_SERVICE_URL='http://media.example.test/service'):
            with self.assertRaises(ServiceError):
                WhisperClient(self.user)
