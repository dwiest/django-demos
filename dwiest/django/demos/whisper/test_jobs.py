from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import Client, TestCase

from .client import ServiceError
from .tests import FILE, FILE_ID

ROOT = '/django/demos/whisper/'
JOB_ID = 'b' * 32
JOB = {'job_id':JOB_ID, 'file_id':FILE_ID, 'display_name':'Meeting', 'status':'queued', 'stage':'waiting',
    'created_at':1800000000, 'updated_at':1800000000, 'attempts':0, 'active':True, 'retention_days':365,
    'options':{'model':'base','language':'','task':'transcribe','word_timestamps':False,'temperature':0,
               'beam_size':5,'condition_on_previous_text':True,'initial_prompt':''}}
PAYLOAD = {'operation_key':'c'*32, 'model':'base','language':'en','task':'transcribe','temperature':'0.5',
           'beam_size':'5','condition_on_previous_text':'on','initial_prompt':'Acme terminology','retention_days':'90'}


class TranscriptionViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='transcriber', password='test')
        self.user.user_permissions.add(Permission.objects.get(content_type__app_label='demos', codename='access_whisper'))
        self.client.force_login(self.user)
        self.mock = patch('dwiest.django.demos.whisper.job_views.WhisperClient').start()
        self.addCleanup(patch.stopall)
        self.service = self.mock.return_value

    def test_form_displays_options_and_requires_no_api_key(self):
        self.service.request.return_value = {'file':FILE}
        response = self.client.get(ROOT+'files/'+FILE_ID+'/transcribe/')
        self.assertContains(response, 'Queue transcription')
        self.assertContains(response, 'Vocabulary or initial context')
        self.assertEqual(len(response.context['form']['operation_key'].value()), 32)
        self.assertNotContains(response, 'name="api_key"')
        self.mock.assert_called_with(self.user)

    def test_submission_uses_stable_operation_key_and_saved_options(self):
        self.service.request.side_effect = [{'file':FILE},{'job':JOB}]
        response = self.client.post(ROOT+'files/'+FILE_ID+'/transcribe/', PAYLOAD)
        self.assertRedirects(response, ROOT+'jobs/'+JOB_ID+'/', fetch_redirect_response=False)
        args = self.service.request.call_args[0]
        self.assertEqual(args[0:2], ('POST','/jobs'))
        self.assertEqual(args[2]['file_id'], FILE_ID)
        self.assertEqual(args[2]['options']['temperature'], 0.5)
        self.assertEqual(args[2]['retention_days'], 90)
        self.assertEqual(args[3], 'c'*32)

    def test_uncertain_submission_preserves_key_and_options(self):
        self.service.request.side_effect = [{'file':FILE}, ServiceError('Connection interrupted.')]
        response = self.client.post(ROOT+'files/'+FILE_ID+'/transcribe/', PAYLOAD)
        self.assertContains(response, 'Connection interrupted.')
        self.assertEqual(response.context['form']['operation_key'].value(), 'c'*32)
        self.assertContains(response, 'Acme terminology')

    def test_invalid_translation_and_unverified_file_do_not_submit(self):
        self.service.request.return_value = {'file':FILE}
        response = self.client.post(ROOT+'files/'+FILE_ID+'/transcribe/', dict(PAYLOAD, model='turbo', task='translate'))
        self.assertContains(response, 'Translation needs a multilingual model other than turbo.')
        self.assertEqual(self.service.request.call_count, 1)
        self.service.request.return_value = {'file':dict(FILE,status='uploading')}
        self.assertEqual(self.client.get(ROOT+'files/'+FILE_ID+'/transcribe/').status_code, 409)

    def test_history_and_filtered_history_are_authenticated(self):
        self.service.request.return_value = {'jobs':[JOB], 'next_cursor':'next-page'}
        self.assertContains(self.client.get(ROOT+'jobs/'), 'Meeting')
        self.assertContains(self.client.get(ROOT+'files/'+FILE_ID+'/jobs/'), 'Older jobs')
        self.service.request.assert_called_with('GET','/files/'+FILE_ID+'/jobs')
        self.user.user_permissions.clear()
        self.mock.reset_mock()
        self.assertEqual(self.client.get(ROOT+'jobs/').status_code, 403)
        self.mock.assert_not_called()

    def test_review_escapes_transcript_and_shows_downloads(self):
        job = dict(JOB,status='completed', active=False, summary={'audio_duration_seconds':0.5,'language':'en','segment_count':1})
        self.service.request.side_effect = [{'job':job}, {'text':'<script>alert(1)</script>', 'preview_truncated':True,
            'downloads':{'txt':'https://storage.example.test/transcript.txt','json':'https://storage.example.test/transcript.json'}}]
        response = self.client.get(ROOT+'jobs/'+JOB_ID+'/')
        self.assertContains(response, '&lt;script&gt;alert(1)&lt;/script&gt;')
        self.assertNotContains(response, '<script>alert(1)</script>')
        self.assertContains(response, 'Download JSON')
        self.assertContains(response, 'first 200,000 bytes')
        self.assertNotContains(response, 'data-job-poll=')

    def test_active_job_polls_without_retrieving_transcript(self):
        self.service.request.return_value = {'job':JOB}
        response = self.client.get(ROOT+'jobs/'+JOB_ID+'/')
        self.assertContains(response, 'data-job-poll=')
        self.assertEqual(self.service.request.call_count, 1)
        response = self.client.get(ROOT+'jobs/'+JOB_ID+'/status/')
        self.assertEqual(response.json()['job']['status'], 'queued')
        self.assertIn('no-store', response['Cache-Control'])

    def test_cancel_delete_confirmation_and_post_only_mutations(self):
        self.service.request.return_value = {'job':JOB}
        for action in ('cancel','delete'):
            url = ROOT+'jobs/'+JOB_ID+'/'+action+'/'
            self.service.request.reset_mock()
            self.assertEqual(self.client.get(url).status_code, 200)
            self.assertEqual(self.service.request.call_count, 1)
            self.assertEqual(self.client.post(url).status_code, 302)
            if action == 'cancel':
                self.service.request.assert_called_with('POST','/jobs/'+JOB_ID+'/cancel',{})
            else:
                self.service.request.assert_called_with('DELETE','/jobs/'+JOB_ID)
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.assertEqual(client.post(ROOT+'jobs/'+JOB_ID+'/cancel/').status_code, 403)
        self.assertEqual(client.post(ROOT+'files/'+FILE_ID+'/transcribe/',PAYLOAD).status_code, 403)

    def test_other_owner_job_and_poll_failures_are_reported(self):
        self.service.request.side_effect = ServiceError('Job not found.',404)
        self.assertEqual(self.client.get(ROOT+'jobs/'+JOB_ID+'/').status_code,404)
        self.assertEqual(self.client.get(ROOT+'jobs/'+JOB_ID+'/status/').status_code,404)
