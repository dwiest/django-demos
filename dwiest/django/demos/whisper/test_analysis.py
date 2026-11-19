from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase, SimpleTestCase, override_settings
from .forms import AISettingsForm
from .tests import FILE_ID
from .test_jobs import JOB_ID, JOB
from .analysis_defaults import DEFAULT_INSTRUCTIONS

PROPOSAL={'title':'Meeting','summary':'Summary','key_points':['Point'],'decisions':[],
          'action_items':['Prepare draft'],'open_questions':[],'warnings':[]}
ROOT='/django/demos/whisper/'
ANALYSIS='d'*32

class ModelFormTests(SimpleTestCase):
    @override_settings(BOOKMARKS_AI_MODELS=['bookmark-model'])
    def test_dropdown_reuses_bookmarks_and_custom_model_wins(self):
        form=AISettingsForm({'model_choice':'bookmark-model'})
        self.assertTrue(form.is_valid(),form.errors)
        self.assertEqual(form.cleaned_data['model'],'bookmark-model')
        form=AISettingsForm({'model_choice':'bookmark-model','model':'custom-model'})
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['model'],'custom-model')
        form=AISettingsForm(initial={'model':'bookmark-model'})
        self.assertEqual(form.initial['model_choice'],'bookmark-model')
        self.assertEqual(form.initial['model'],'')

class AnalysisViewTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_user(username='reviewer')
        self.user.user_permissions.add(Permission.objects.get(content_type__app_label='demos',codename='access_whisper'))
        self.client.force_login(self.user)
        self.factory=patch('dwiest.django.demos.whisper.analysis_views.WhisperClient').start()
        self.addCleanup(patch.stopall)
        self.api=self.factory.return_value
        self.analysis=dict(JOB,job_id=ANALYSIS,type='transcript.analyze',source_job_id=JOB_ID,status='completed',review_status='pending')

    def test_queue_explicitly_sends_per_job_instructions_and_operation_key(self):
        self.api.request.side_effect=[{'job':dict(JOB,status='completed',type='media.transcribe')},{'job':self.analysis}]
        response=self.client.post(ROOT+'jobs/'+JOB_ID+'/analyze/',{'operation_key':'e'*32,'instructions':'Extract tasks','retention_days':30})
        self.assertEqual(response.status_code,302)
        self.api.request.assert_called_with('POST','/jobs/'+JOB_ID+'/analyze',{'instructions':'Extract tasks','retention_days':30},'e'*32)

    def test_review_lists_edit_and_approve_without_model_call(self):
        self.api.request.return_value={'job':self.analysis,'proposal':PROPOSAL}
        path=ROOT+'jobs/'+ANALYSIS+'/review/'
        self.assertContains(self.client.get(path),'Approve edited analysis')
        values={k:'\n'.join(v) if isinstance(v,list) else v for k,v in PROPOSAL.items()}
        response=self.client.post(path,dict(values,summary='Edited',action='approve'))
        self.assertEqual(response.status_code,302)
        self.assertEqual(self.api.request.call_args[0][2]['proposal']['action_items'],['Prepare draft'])
        self.assertEqual(self.api.request.call_args[0][2]['proposal']['summary'],'Edited')
        self.assertEqual(self.api.request.call_args[0][1],'/jobs/'+ANALYSIS+'/review')

    def test_test_button_does_not_save_and_default_does_not_replace_custom_instructions(self):
        with patch('dwiest.django.demos.whisper.ai_views.WhisperClient') as factory:
            api=factory.return_value
            api.request.return_value={'has_api_key':True,'model':'custom-model','instructions':'My instructions'}
            response=self.client.get(ROOT+'ai/settings/')
            self.assertContains(response,'My instructions')
            self.assertContains(response,'Test connection')
            api.request.side_effect=[{'has_api_key':True,'model':'custom-model','instructions':'My instructions'}, {'message':'Connection succeeded'}]
            response=self.client.post(ROOT+'ai/settings/',{'action':'test','model':'custom-model','api_key':'test-unsaved-secret-key'},HTTP_ACCEPT='application/json')
            self.assertEqual(response.json()['message'],'Connection succeeded')
            api.request.assert_called_with('POST','/ai/test',{'model':'custom-model','api_key':'test-unsaved-secret-key'})
            self.assertNotContains(response,'test-unsaved-secret-key')
