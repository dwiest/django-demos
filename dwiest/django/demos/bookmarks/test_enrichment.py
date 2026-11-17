import io
import json
from datetime import timedelta
from unittest.mock import Mock, patch
from urllib.error import HTTPError

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from botocore.credentials import Credentials

from ..bookmark_ai_models import BookmarkAISettings, BookmarkAIAnalysis, BookmarkEnrichmentAttempt
from .ai_credentials import AIError
from .ai_views import snapshot
from .enrichment import advance, start
from .job_client import JobClient, JobError, connection
from .models import Bookmark, Tag

URL = 'https://example.com/article'
BASE = 'https://jobs.example.com/service'
RETRIEVAL = 'a' * 32
ANALYSIS = 'b' * 32
PROPOSAL = {'title': 'Source title', 'description': 'Opening paragraph summary.', 'article_date': None, 'tags': ['Python']}


@override_settings(BOOKMARKS_JOB_SERVICE_URL=BASE, BOOKMARKS_JOB_SERVICE_REGION='us-east-1')
class EnrichmentTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('owner')
        self.other = get_user_model().objects.create_user('other')
        config = override_settings(BOOKMARKS_API_OWNER_ID=self.user.pk)
        config.enable(); self.addCleanup(config.disable)
        self.client.force_login(self.user)
        self.bookmark = Bookmark.objects.create(owner=self.user, url=URL, title='Original', description='Original text')
        self.prefs = BookmarkAISettings.objects.create(owner=self.user, use_job_service=True)
        self.original = {'persisted': snapshot(self.bookmark), 'draft': snapshot(self.bookmark)}
        network = patch('dwiest.django.demos.bookmarks.job_client.build_opener', side_effect=AssertionError('Unexpected network'))
        network.start(); self.addCleanup(network.stop)

    def attempt(self, **kwargs):
        return start(self.user, self.bookmark, self.original, URL, **kwargs)

    def complete(self, attempt):
        client = Mock()
        client.submit.side_effect = [{'job_id': RETRIEVAL, 'reused': True}, {'job_id': ANALYSIS}]
        client.job.side_effect = [
            {'status': 'completed'}, {'result': {'retrieved': True, 'title': 'Source title', 'text': 'Captured text', 'final_url': URL, 'http_status': 200}},
            {'status': 'completed'}, {'result': {'proposal': PROPOSAL, 'capture_id': RETRIEVAL, 'analysis_id': ANALYSIS, 'model': 'test-model'}}]
        with patch('dwiest.django.demos.bookmarks.enrichment.JobClient', return_value=client):
            for _ in range(4):
                attempt = advance(attempt.pk)
        return attempt, client

    def url(self, attempt):
        return reverse('demos:bookmarks:enrichment', args=[attempt.pk])

    def test_full_flow_requires_explicit_approval_and_keeps_references(self):
        attempt, remote = self.complete(self.attempt())
        self.assertEqual(attempt.status, 'ready')
        self.assertEqual((attempt.retrieval_job_id, attempt.analysis_job_id), (RETRIEVAL, ANALYSIS))
        self.assertNotIn('text', attempt.retrieval)
        self.bookmark.refresh_from_db()
        self.assertEqual(self.bookmark.title, 'Original')
        self.assertFalse(Tag.objects.filter(title='Python').exists())
        review = attempt.review
        self.assertEqual(review.sources[0]['capture_id'], RETRIEVAL)
        self.assertEqual(self.client.get(self.url(attempt)).status_code, 200)
        opened = self.client.post(self.url(attempt), {'action': 'review'})
        self.assertRedirects(opened, reverse('demos:bookmarks:ai_review', args=[review.pk]))
        result = self.client.post(opened.url, dict(PROPOSAL, url=URL, tags='Python', article_date='',
            selected=['title', 'description', 'tags'], action='apply'))
        self.assertEqual(result.status_code, 302)
        self.bookmark.refresh_from_db()
        self.assertEqual(self.bookmark.title, 'Source title')
        self.assertTrue(Tag.objects.filter(owner=self.user, title='Python').exists())
        self.assertEqual(remote.submit.call_count, 2)

    def test_repeat_start_reuses_local_operation(self):
        first = self.attempt()
        self.assertEqual(self.attempt().pk, first.pk)
        self.assertEqual(BookmarkEnrichmentAttempt.objects.count(), 1)
        self.assertEqual(Bookmark.objects.count(), 1)

    def test_download_only_stops_before_analysis(self):
        attempt = self.attempt(mode='download')
        remote = Mock()
        remote.submit.return_value = {'job_id': RETRIEVAL}
        remote.job.side_effect = [{'status': 'completed'}, {'result': {'retrieved': True, 'text': 'Article'}}]
        with patch('dwiest.django.demos.bookmarks.enrichment.JobClient', return_value=remote):
            advance(attempt.pk); result = advance(attempt.pk)
        self.assertEqual(result.status, 'downloaded')
        self.assertEqual(remote.submit.call_count, 1)
        self.assertFalse(BookmarkAIAnalysis.objects.exists())

    def test_unavailable_content_does_not_trigger_analysis(self):
        attempt = self.attempt()
        remote = Mock()
        remote.submit.return_value = {'job_id': RETRIEVAL}
        remote.job.side_effect = [{'status': 'completed'}, {'result': {'retrieved': False, 'failure_reason': 'access_denied', 'http_status': 403, 'failure_message': 'Site returned HTTP 403.'}}]
        with patch('dwiest.django.demos.bookmarks.enrichment.JobClient', return_value=remote):
            advance(attempt.pk); attempt = advance(attempt.pk)
        self.assertEqual(attempt.status, 'failed')
        self.assertEqual(attempt.error['http_status'], 403)
        self.assertEqual(remote.submit.call_count, 1)
        self.assertFalse(BookmarkAIAnalysis.objects.exists())

    def test_transport_retry_keeps_submission_key(self):
        attempt = self.attempt()
        remote = Mock()
        remote.submit.side_effect = [JobError('Temporary outage', 503), {'job_id': RETRIEVAL}]
        with patch('dwiest.django.demos.bookmarks.enrichment.JobClient', return_value=remote):
            first = advance(attempt.pk)
            self.assertEqual(first.status, 'retrieval_pending')
            self.assertIsNotNone(first.retry_after)
            advance(attempt.pk)
            self.assertEqual(remote.submit.call_count, 1)
            BookmarkEnrichmentAttempt.objects.filter(pk=attempt.pk).update(retry_after=None)
            advance(attempt.pk)
        self.assertEqual(remote.submit.call_args_list[0], remote.submit.call_args_list[1])

    def test_lease_prevents_duplicate_advancement_and_get_has_no_side_effect(self):
        attempt = self.attempt()
        BookmarkEnrichmentAttempt.objects.filter(pk=attempt.pk).update(lease_until=timezone.now()+timedelta(seconds=90))
        with patch('dwiest.django.demos.bookmarks.enrichment.JobClient') as remote:
            advance(attempt.pk)
            self.client.get(self.url(attempt))
            remote.assert_not_called()
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.user)
        self.assertEqual(csrf.post(self.url(attempt), {'action':'advance'}).status_code, 403)

    def test_other_owner_cannot_read_or_advance_attempt(self):
        attempt = self.attempt()
        self.client.force_login(self.other)
        with override_settings(BOOKMARKS_API_OWNER_ID=self.other.pk):
            self.assertEqual(self.client.get(self.url(attempt)).status_code, 404)
            self.assertEqual(self.client.post(self.url(attempt), {'action':'advance'}).status_code, 404)

    def test_changed_bookmark_is_not_overwritten_by_saved_proposal(self):
        attempt, _ = self.complete(self.attempt())
        self.bookmark.title = 'Manual edit'; self.bookmark.save()
        result = self.client.post(reverse('demos:bookmarks:ai_review', args=[attempt.review_id]),
            dict(PROPOSAL, url=URL, tags='Python', article_date='', selected=['title'], action='apply'))
        self.assertContains(result, 'changed after analysis')
        self.bookmark.refresh_from_db()
        self.assertEqual(self.bookmark.title, 'Manual edit')

    def test_expired_review_reopens_without_another_analysis(self):
        attempt, _ = self.complete(self.attempt())
        BookmarkAIAnalysis.objects.filter(pk=attempt.review_id).update(expires_at=timezone.now()-timedelta(minutes=1))
        with patch('dwiest.django.demos.bookmarks.enrichment.JobClient') as remote:
            self.client.post(self.url(attempt), {'action':'review'})
            remote.assert_not_called()
        attempt.review.refresh_from_db()
        self.assertGreater(attempt.review.expires_at, timezone.now())

    def test_deleted_review_can_be_recreated_from_saved_proposal(self):
        attempt, _ = self.complete(self.attempt())
        attempt.review.delete()
        with patch('dwiest.django.demos.bookmarks.enrichment.JobClient') as remote:
            response = self.client.post(self.url(attempt), {'action':'review'})
            remote.assert_not_called()
        self.assertEqual(response.status_code, 302)
        attempt.refresh_from_db()
        self.assertEqual(attempt.review.proposal['title'], PROPOSAL['title'])

    def test_explicit_retry_is_repeatable_without_creating_more_attempts(self):
        attempt, _ = self.complete(self.attempt())
        first = self.client.post(self.url(attempt), {'action':'retry_download'})
        second = self.client.post(self.url(attempt), {'action':'retry_download'})
        self.assertEqual(first.url, second.url)
        retry = BookmarkEnrichmentAttempt.objects.exclude(pk=attempt.pk).get()
        self.assertTrue(retry.request_options['force_refresh'])
        remote = Mock(); remote.submit.return_value = {'job_id': RETRIEVAL}
        with patch('dwiest.django.demos.bookmarks.enrichment.JobClient', return_value=remote):
            advance(retry.pk)
        self.assertTrue(remote.submit.call_args[0][0]['request']['force_refresh'])

    def test_analysis_key_reuses_same_capture_and_configuration(self):
        one = self.attempt()
        original = dict(self.original, draft=dict(self.original['draft'], description='Different draft'))
        two = start(self.user, self.bookmark, original, URL)
        self.assertNotEqual(one.pk, two.pk)
        remote = Mock(); remote.submit.side_effect = [{'job_id':RETRIEVAL},{'job_id':RETRIEVAL},{'job_id':ANALYSIS},{'job_id':ANALYSIS}]
        remote.job.return_value = {'status':'completed'}
        with patch('dwiest.django.demos.bookmarks.enrichment.JobClient', return_value=remote):
            advance(one.pk); advance(two.pk)
            remote.job.side_effect = [{'status':'completed'},{'result':{'retrieved':True}}, {'status':'completed'},{'result':{'retrieved':True}}]
            advance(one.pk); advance(two.pk)
            advance(one.pk); advance(two.pk)
        self.assertEqual(remote.submit.call_args_list[2][0][1], remote.submit.call_args_list[3][0][1])

    def test_management_command_advances_without_browser(self):
        attempt = self.attempt()
        remote = Mock(); remote.submit.return_value = {'job_id': RETRIEVAL}
        with patch('dwiest.django.demos.bookmarks.enrichment.JobClient', return_value=remote):
            call_command('advance_bookmark_enrichment', stdout=io.StringIO())
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, 'retrieving')

    def test_existing_url_opens_owned_bookmark_without_overwriting(self):
        response = self.client.post(reverse('demos:bookmarks:bookmark'), {'url': 'https://EXAMPLE.com:443/article#section', 'title':'Overwrite', 'status':0})
        self.assertEqual(response.status_code, 302)
        self.assertIn('id='+str(self.bookmark.pk), response.url)
        self.assertEqual(Bookmark.objects.count(), 1)
        self.bookmark.refresh_from_db(); self.assertEqual(self.bookmark.title, 'Original')

    def test_job_settings_use_server_endpoint_and_sync_retention(self):
        with patch('dwiest.django.demos.bookmarks.job_client.JobClient') as remote:
            response = self.client.post(reverse('demos:bookmarks:ai_settings'), {'action':'save_job_service', 'use_job_service':'on', 'include_raw_html':'on', 'keep_indefinitely':'on'})
        self.assertEqual(response.status_code, 302)
        remote.return_value.request.assert_called_once_with('POST','/retention',{'days':None})
        self.prefs.refresh_from_db()
        self.assertIsNone(self.prefs.job_retention_days)
        self.assertTrue(self.prefs.use_job_service)

    def test_editor_starts_job_service_without_direct_ai_key(self):
        with patch('dwiest.django.demos.bookmarks.ai_views.api_key_for', side_effect=AssertionError('No direct key needed')):
            response = self.client.post(reverse('demos:bookmarks:bookmark'), {'id':self.bookmark.pk, 'url':URL, 'title':'Draft title','status':'0', 'action':'ai_analyze'})
        self.assertEqual(response.status_code, 302)
        attempt = BookmarkEnrichmentAttempt.objects.get()
        self.assertIn(str(attempt.pk), response.url)
        self.assertEqual(attempt.original['draft']['title'], 'Draft title')
        self.bookmark.refresh_from_db(); self.assertEqual(self.bookmark.title, 'Original')


    def test_analyze_downloaded_content_pins_exact_capture(self):
        attempt = self.attempt(mode='download')
        attempt.status = 'downloaded'
        attempt.retrieval_job_id = RETRIEVAL
        attempt.retrieval = {'retrieved': True, 'title': 'Saved title'}
        attempt.save()
        response = self.client.post(self.url(attempt), {'action': 'analyze'})
        selected = BookmarkEnrichmentAttempt.objects.exclude(pk=attempt.pk).get()
        self.assertEqual(selected.status, 'analysis_pending')
        self.assertEqual(selected.retrieval_job_id, RETRIEVAL)
        self.assertRedirects(response, self.url(selected))
        remote = Mock()
        remote.submit.return_value = {'job_id': ANALYSIS}
        with patch('dwiest.django.demos.bookmarks.enrichment.JobClient', return_value=remote):
            advance(selected.pk)
        self.assertEqual(remote.submit.call_count, 1)
        self.assertEqual(remote.submit.call_args[0][0]['type'], 'ai.analyze')
        self.assertEqual(remote.submit.call_args[0][0]['request']['capture_id'], RETRIEVAL)


    def test_download_cannot_fall_back_to_billable_direct_analysis(self):
        self.prefs.use_job_service = False
        self.prefs.save()
        with patch('dwiest.django.demos.bookmarks.ai_views.ai_service.analyze', side_effect=AssertionError('No direct analysis')):
            response = self.client.post(reverse('demos:bookmarks:bookmark'), {'id':self.bookmark.pk, 'url':URL, 'status':'0', 'action':'job_download'})
        self.assertContains(response, 'Enable the job service')


    def test_submission_failure_offers_analysis_retry_without_an_analysis_id(self):
        attempt = self.attempt()
        attempt.status = 'analysis_pending'
        attempt.retrieval_job_id = RETRIEVAL
        attempt.retrieval = {'retrieved': True}
        attempt.save()
        remote = Mock()
        remote.submit.side_effect = JobError('AI analysis is not configured.', 400)
        with patch('dwiest.django.demos.bookmarks.enrichment.JobClient', return_value=remote):
            failed = advance(attempt.pk)
        self.assertEqual(failed.status, 'failed')
        self.assertFalse(failed.analysis_job_id)
        self.assertContains(self.client.get(self.url(failed)), 'value="retry_analysis"')
        one = self.client.post(self.url(failed), {'action':'retry_analysis'})
        two = self.client.post(self.url(failed), {'action':'retry_analysis'})
        self.assertEqual(one.url, two.url)
        retry = BookmarkEnrichmentAttempt.objects.exclude(pk=failed.pk).get()
        self.assertEqual(retry.status, 'analysis_pending')
        self.assertEqual(retry.retrieval_job_id, RETRIEVAL)

    def test_service_failure_message_is_preserved(self):
        attempt = self.attempt()
        attempt.status = 'analyzing'
        attempt.analysis_job_id = ANALYSIS
        attempt.save()
        failure = {'code':'analysis_secret_access_error', 'message':'Worker cannot read secret.',
                   'diagnostics':{'aws_error_code':'AccessDeniedException'}}
        remote = Mock()
        remote.job.return_value = {'status':'failed', 'error':failure}
        with patch('dwiest.django.demos.bookmarks.enrichment.JobClient', return_value=remote):
            result = advance(attempt.pk)
        self.assertEqual(result.error, failure)
        self.assertContains(self.client.get(self.url(result)), 'AccessDeniedException')

    def test_resume_polls_existing_job_without_submitting(self):
        attempt = self.attempt()
        attempt.status = 'failed'
        attempt.analysis_job_id = ANALYSIS
        attempt.error = {'http_status':403}
        attempt.save()
        with patch('dwiest.django.demos.bookmarks.enrichment.JobClient') as remote:
            self.client.post(self.url(attempt), {'action':'resume_analysis'})
            remote.assert_not_called()
        attempt.refresh_from_db()
        self.assertEqual(attempt.status, 'analyzing')
        self.assertEqual(attempt.analysis_job_id, ANALYSIS)
        self.assertEqual(attempt.error, {})

    def test_progress_updates_ids_and_explains_lease(self):
        attempt = self.attempt()
        attempt.status = 'analyzing'
        attempt.retrieval_job_id = RETRIEVAL
        attempt.analysis_job_id = ANALYSIS
        attempt.lease_until = timezone.now() + timedelta(seconds=60)
        attempt.save()
        with patch('dwiest.django.demos.bookmarks.enrichment.JobClient') as remote:
            data = self.client.post(self.url(attempt), {'action':'advance'}).json()
            remote.assert_not_called()
        self.assertEqual(data['analysis_job_id'], ANALYSIS)
        self.assertEqual(data['retrieval_job_id'], RETRIEVAL)
        self.assertIn('lease', data['message'])
        self.assertGreater(data['poll_after_seconds'], 3)

    def test_status_command_explains_skipped_attempt_without_network(self):
        attempt = self.attempt()
        attempt.lease_until = timezone.now() + timedelta(seconds=60)
        attempt.save()
        with patch('dwiest.django.demos.bookmarks.enrichment.JobClient') as remote:
            output = io.StringIO()
            call_command('advance_bookmark_enrichment', attempt=str(attempt.pk), status_only=True, stdout=output)
            self.assertIn('lease_until', output.getvalue())
            output = io.StringIO()
            call_command('advance_bookmark_enrichment', attempt=str(attempt.pk), stdout=output)
            self.assertIn('No due attempts', output.getvalue())
            remote.assert_not_called()



@override_settings(BOOKMARKS_JOB_SERVICE_URL=BASE, BOOKMARKS_JOB_SERVICE_REGION='us-east-1')
class JobClientTests(TestCase):
    def test_signs_server_controlled_endpoint_with_user_reference(self):
        response = Mock(); response.__enter__ = Mock(return_value=response); response.__exit__ = Mock(return_value=False)
        response.read.return_value = b'{"job_id":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}'
        session = Mock(); session.get_credentials.return_value = Credentials('test-access','test-secret','test-session')
        with patch('dwiest.django.demos.bookmarks.job_client.boto3.Session',return_value=session), patch('dwiest.django.demos.bookmarks.job_client.build_opener') as opener:
            opener.return_value.open.return_value = response
            JobClient(Mock(pk=42)).submit({'type':'web.retrieve'}, 'stable-key')
        request = opener.return_value.open.call_args[0][0]
        self.assertEqual(request.full_url, BASE+'/jobs')
        headers = {k.lower():v for k,v in request.header_items()}
        self.assertEqual(headers['x-user-reference'],'42')
        self.assertEqual(headers['idempotency-key'],'stable-key')
        self.assertIn('execute-api/aws4_request', headers['authorization'])
        self.assertNotIn('test-secret',str(headers))

    def test_endpoint_and_saved_endpoint_must_match_configuration(self):
        with override_settings(BOOKMARKS_JOB_SERVICE_URL='http://example.com/service'), self.assertRaises(AIError):
            connection()
        with self.assertRaises(AIError):
            JobClient(Mock(pk=42), 'https://other.example.com/service')
