from datetime import timedelta
from unittest.mock import patch, Mock
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from django.core.management import call_command
from ..bookmark_ai_models import BookmarkAISettings, BookmarkEnrichmentAttempt
from .models import Bookmark, Tag
from .ai_views import snapshot
from .enrichment import start, advance
from .history import cleanup_failed
from . import test_enrichment as fixtures
from .test_enrichment import URL, BASE, PROPOSAL, RETRIEVAL, ANALYSIS


@override_settings(BOOKMARKS_JOB_SERVICE_URL=BASE, BOOKMARKS_JOB_SERVICE_REGION='us-east-1')
class CreationHistoryTests(TestCase):
    setUp = fixtures.EnrichmentTests.setUp
    complete = fixtures.EnrichmentTests.complete
    url = fixtures.EnrichmentTests.url

    def auto(self):
        return start(self.user, self.bookmark, self.original, URL, auto_apply=True)

    def test_creation_persists_before_work_and_duplicate_does_not_resubmit(self):
        self.bookmark.delete()
        payload = {'url':URL, 'title':'', 'status':'0', 'enrich_content':'on'}
        with patch('dwiest.django.demos.bookmarks.enrichment.JobClient') as remote:
            response = self.client.post(reverse('demos:bookmarks:bookmark'), payload)
            remote.assert_not_called()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Bookmark.objects.count(), 1)
        attempt = BookmarkEnrichmentAttempt.objects.get()
        self.assertTrue(attempt.request_options['auto_apply'])
        self.assertEqual(attempt.status, 'retrieval_pending')
        self.client.post(reverse('demos:bookmarks:bookmark'), payload)
        self.assertEqual(BookmarkEnrichmentAttempt.objects.count(), 1)
        self.assertEqual(Bookmark.objects.count(), 1)

    def test_automatic_apply_preserves_entered_fields_and_adds_tags(self):
        attempt, remote = self.complete(self.auto())
        self.assertEqual(attempt.status, 'applied')
        self.bookmark.refresh_from_db()
        self.assertEqual(self.bookmark.title, 'Original')
        self.assertEqual(self.bookmark.description, 'Original text')
        self.assertTrue(Tag.objects.filter(owner=self.user, title='Python').exists())
        self.assertEqual(attempt.review.status, 'applied')
        with patch('dwiest.django.demos.bookmarks.enrichment.JobClient') as api:
            advance(attempt.pk)
            api.assert_not_called()

    def test_blank_fields_are_filled(self):
        self.bookmark.title = ''; self.bookmark.description = ''; self.bookmark.save()
        original = snapshot(self.bookmark)
        attempt = start(self.user, self.bookmark, {'persisted':original, 'draft':original}, URL, auto_apply=True)
        attempt, _ = self.complete(attempt)
        self.assertEqual(attempt.status, 'applied')
        self.bookmark.refresh_from_db()
        self.assertEqual(self.bookmark.title, PROPOSAL['title'])
        self.assertEqual(self.bookmark.description, PROPOSAL['description'])

    def test_edit_during_work_requires_review_against_current_values(self):
        attempt = self.auto()
        self.bookmark.title = 'Edited during analysis'; self.bookmark.save()
        attempt, _ = self.complete(attempt)
        self.assertEqual(attempt.status, 'ready')
        self.assertEqual(attempt.review.original['persisted']['title'], 'Edited during analysis')
        self.assertIn('needs_review_reason', attempt.analysis)
        self.bookmark.refresh_from_db()
        self.assertEqual(self.bookmark.title, 'Edited during analysis')
        self.assertFalse(Tag.objects.filter(title='Python').exists())

    def test_manual_creation_does_not_start_enrichment(self):
        self.bookmark.delete()
        response = self.client.post(reverse('demos:bookmarks:bookmark'), {'url':URL, 'title':'Manual', 'status':'0'})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(BookmarkEnrichmentAttempt.objects.exists())

    def test_download_only_does_not_authorize_analysis_or_apply(self):
        self.bookmark.delete()
        self.client.post(reverse('demos:bookmarks:bookmark'), {'url':URL, 'title':'Downloaded', 'status':'0', 'download_content':'on'})
        attempt = BookmarkEnrichmentAttempt.objects.get()
        self.assertEqual(attempt.mode, 'download')
        self.assertFalse(attempt.request_options.get('auto_apply'))

    def test_pending_work_times_out_locally(self):
        attempt = self.auto()
        BookmarkEnrichmentAttempt.objects.filter(pk=attempt.pk).update(created_at=timezone.now()-timedelta(hours=4))
        with patch('dwiest.django.demos.bookmarks.enrichment.JobClient') as api:
            attempt = advance(attempt.pk)
            api.assert_not_called()
        self.assertEqual(attempt.error['code'], 'workflow_timeout')

    def failed(self):
        attempt = self.auto()
        attempt.status = 'failed'; attempt.save()
        return attempt

    def history(self):
        return reverse('demos:bookmarks:enrichment_history')

    def test_history_cleanup_requires_confirmation_and_preserves_remote_data(self):
        attempt = self.failed()
        with patch('dwiest.django.demos.bookmarks.enrichment.JobClient') as api:
            response = self.client.post(self.history(), {'action':'preview_failed'})
            self.assertTrue(BookmarkEnrichmentAttempt.objects.filter(pk=attempt.pk).exists())
            token = response.context['confirmation']['token']
            self.client.post(self.history(), {'action':'confirm', 'token':token})
            api.assert_not_called()
        self.assertFalse(BookmarkEnrichmentAttempt.objects.filter(pk=attempt.pk).exists())
        self.assertTrue(Bookmark.objects.filter(pk=self.bookmark.pk).exists())

    def test_history_preview_does_not_delete_changed_or_other_owner_records(self):
        attempt = self.failed()
        response = self.client.post(self.history(), {'action':'preview_failed'})
        token = response.context['confirmation']['token']
        attempt.status = 'retrieving'; attempt.save()
        self.client.post(self.history(), {'action':'confirm', 'token':token})
        self.assertTrue(BookmarkEnrichmentAttempt.objects.filter(pk=attempt.pk).exists())
        self.client.force_login(self.other)
        with override_settings(BOOKMARKS_API_OWNER_ID=self.other.pk):
            self.client.post(self.history(), {'action':'confirm', 'token':token})
        self.assertTrue(BookmarkEnrichmentAttempt.objects.filter(pk=attempt.pk).exists())

    def test_expiration_is_per_user_and_indefinite_is_supported(self):
        attempt = self.failed()
        BookmarkEnrichmentAttempt.objects.filter(pk=attempt.pk).update(updated_at=timezone.now()-timedelta(days=31))
        self.prefs.failed_attempt_retention_days = None; self.prefs.save()
        self.assertEqual(cleanup_failed(), 0)
        self.prefs.failed_attempt_retention_days = 30; self.prefs.save()
        self.assertEqual(cleanup_failed(), 1)

    def test_successful_pending_review_is_never_purged(self):
        attempt, _ = self.complete(start(self.user, self.bookmark, self.original, URL))
        BookmarkEnrichmentAttempt.objects.filter(pk=attempt.pk).update(updated_at=timezone.now()-timedelta(days=400))
        self.assertEqual(cleanup_failed(), 0)
        response = self.client.post(self.history(), {'action':'preview_remove', 'attempt':str(attempt.pk)})
        self.assertEqual(response.context['confirmation']['count'], 0)

    def test_history_paginates_all_attempts(self):
        for n in range(27):
            BookmarkEnrichmentAttempt.objects.create(owner=self.user, bookmark_id=self.bookmark.pk,
                fingerprint=str(n), url=URL, service_url=BASE, status='failed')
        response = self.client.get(self.history())
        self.assertEqual(response.context['page_obj'].paginator.count, 27)
        self.assertTrue(response.context['page_obj'].has_next())
        self.assertEqual(len(self.client.get(self.history()+'?page=2').context['page_obj']), 2)

    def test_failed_automatic_apply_rolls_back_and_retains_review(self):
        from django.db import IntegrityError
        attempt = self.auto()
        with patch('dwiest.django.demos.bookmarks.creation.apply_proposal', side_effect=IntegrityError('test failure')):
            attempt, _ = self.complete(attempt)
        self.assertEqual(attempt.status, 'ready')
        self.assertEqual(attempt.review.status, 'pending')
        self.bookmark.refresh_from_db()
        self.assertEqual(self.bookmark.title, 'Original')
        self.assertFalse(Tag.objects.filter(title='Python').exists())

    def test_cleanup_requires_csrf(self):
        from django.test import Client
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.assertEqual(client.post(self.history(), {'action':'preview_failed'}).status_code, 403)

    def test_creation_defaults_can_be_enabled_and_history_retention_disabled(self):
        with patch('dwiest.django.demos.bookmarks.job_client.JobClient'):
            response = self.client.post(reverse('demos:bookmarks:ai_settings'), {
                'action':'save_job_service', 'use_job_service':'on', 'enrich_on_create':'on',
                'job_retention_days':'365', 'keep_failed_history':'on'})
        self.assertEqual(response.status_code, 302)
        self.prefs.refresh_from_db()
        self.assertTrue(self.prefs.enrich_on_create)
        self.assertTrue(self.prefs.download_on_create)
        self.assertIsNone(self.prefs.failed_attempt_retention_days)
        page = self.client.get(reverse('demos:bookmarks:bookmark'))
        self.assertTrue(page.context['enrich_on_create'])

    def test_instructions_visible_in_service_mode_and_survive_retries(self):
        self.assertContains(self.client.get(reverse('demos:bookmarks:bookmark')+'?id='+str(self.bookmark.pk)), 'name="ai_instructions"')
        attempt = start(self.user, self.bookmark, self.original, URL, instructions='Focus on databases.')
        attempt.retrieval_job_id = RETRIEVAL; attempt.retrieval = {'retrieved':True}; attempt.status = 'failed'; attempt.save()
        self.client.post(self.url(attempt), {'action':'retry_analysis'})
        retry = BookmarkEnrichmentAttempt.objects.exclude(pk=attempt.pk).get()
        remote = Mock(); remote.submit.return_value = {'job_id':ANALYSIS}
        with patch('dwiest.django.demos.bookmarks.enrichment.JobClient', return_value=remote):
            advance(retry.pk)
        self.assertEqual(remote.submit.call_args[0][0]['request']['instructions'], 'Focus on databases.')

    def test_different_instructions_do_not_reuse_an_operation(self):
        first = start(self.user, self.bookmark, self.original, URL, instructions='Short summary')
        second = start(self.user, self.bookmark, self.original, URL, instructions='Detailed summary')
        self.assertNotEqual(first.pk, second.pk)
        from .ai_credentials import AIError
        with self.assertRaises(AIError):
            start(self.user, self.bookmark, self.original, URL, instructions='x'*4001)
