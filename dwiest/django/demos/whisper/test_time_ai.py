from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import Client, TestCase, SimpleTestCase
from .job_views import job_present
from ..templatetags.whisper_time import elapsed


class TimeTests(SimpleTestCase):
    def test_duration_hours_minutes_seconds_and_legacy_values(self):
        self.assertEqual(elapsed(3661),'1 hour, 1 minute, 1 second')
        self.assertEqual(elapsed(7320),'2 hours, 2 minutes, 0 seconds')
        self.assertEqual(elapsed(0),'0 seconds')
        self.assertEqual(elapsed(None),'Unavailable')
        self.assertEqual(elapsed(float('nan')),'Unavailable')
        job = job_present({'status':'completed','created_at':100,'started_at':120,'completed_at':3781})
        self.assertEqual(job['elapsed_seconds'],3661)
        self.assertEqual(job['queue_seconds'],20)


class AISettingsViewTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_user(username='ai-user')
        self.user.user_permissions.add(Permission.objects.get(content_type__app_label='demos',codename='access_whisper'))
        self.client.force_login(self.user)
        self.mock=patch('dwiest.django.demos.whisper.ai_views.WhisperClient').start()
        self.addCleanup(patch.stopall)
        self.mock.return_value.request.return_value={'has_api_key':True,'model':'test-model','instructions':'Summarize'}

    def test_saved_key_is_not_rendered_and_error_never_repopulates_password(self):
        path='/apps/demos/whisper/ai/settings/'
        self.assertContains(self.client.get(path),'API key: <strong>Saved</strong>')
        key='test-user-secret-key'
        response=self.client.post(path,{'api_key':key,'remove_api_key':'on'})
        self.assertNotContains(response,key)
        self.assertContains(response,'Replace or remove the key')
        client=Client(enforce_csrf_checks=True);client.force_login(self.user)
        self.assertEqual(client.post(path,{'api_key':key}).status_code,403)

    def test_owner_and_settings_save_and_access_guard(self):
        path='/apps/demos/whisper/ai/settings/'
        self.assertEqual(self.client.post(path,{'model':'test-model','instructions':'Custom','api_key':'test-user-secret-key'}).status_code,302)
        self.mock.assert_called_with(self.user)
        self.user.user_permissions.clear()
        self.assertEqual(self.client.get(path).status_code,403)
