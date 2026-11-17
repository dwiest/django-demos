from datetime import timedelta
from unittest.mock import Mock, patch
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from .test_enrichment import BASE, URL, RETRIEVAL, ANALYSIS, PROPOSAL
from . import test_enrichment as fixtures
from .enrichment import start
from .job_client import JobError
from .job_status import decorate
from .models import Bookmark, Tag, BookmarkTag
from ..bookmark_ai_models import BookmarkEnrichmentAttempt, BookmarkAIAnalysis


@override_settings(BOOKMARKS_JOB_SERVICE_URL=BASE, BOOKMARKS_JOB_SERVICE_REGION='us-east-1')
class RecordTests(TestCase):
    setUp = fixtures.EnrichmentTests.setUp
    complete = fixtures.EnrichmentTests.complete

    def saved(self):
        attempt, _ = self.complete(start(self.user, self.bookmark, self.original, URL))
        attempt.retrieval['author'] = 'John Doe'
        attempt.analysis.update(usage={'input_tokens': 100, 'details': {'cached': 20}}, provider_response_id='resp_saved',
                                configuration='bookmark.enrichment.v1', model_requested='test-model', prompt_version='bookmark.enrichment.v2')
        attempt.save()
        return attempt

    def record_url(self, attempt, kind='retrieval'):
        return reverse('demos:bookmarks:job_record', args=[attempt.pk, kind])

    def test_saved_results_downloads_and_provenance_are_linked_and_escaped(self):
        attempt = self.saved()
        page = self.client.get(reverse('demos:bookmarks:enrichment', args=[attempt.pk]))
        self.assertContains(page, self.record_url(attempt))
        self.assertContains(page, self.record_url(attempt, 'analysis') + '#provider_response_id')
        self.assertContains(page, '#service-analysis-settings')
        remote = Mock()
        remote.job.side_effect = [{'job_id': RETRIEVAL, 'status': 'completed'},
            {'result': {'text': '<script>window.pwned=true</script>', 'retrieved': True},
             'downloads': {'text': 'https://bucket.s3.amazonaws.com/article?sig=test', 'bad': 'javascript:alert(1)'}}]
        with patch('dwiest.django.demos.bookmarks.record_views.JobClient', return_value=remote):
            response = self.client.get(self.record_url(attempt))
        self.assertContains(response, '&lt;script&gt;window.pwned=true&lt;/script&gt;')
        self.assertNotContains(response, '<script>window.pwned=true</script>')
        self.assertContains(response, 'Download text')
        self.assertNotContains(response, 'javascript:')
        self.assertEqual(remote.job.call_args_list[0][0], (RETRIEVAL,))
        remote.submit.assert_not_called()

    def test_owner_endpoint_and_job_references_cannot_be_overridden(self):
        attempt = self.saved()
        with patch('dwiest.django.demos.bookmarks.record_views.JobClient') as remote:
            self.client.force_login(self.other)
            with override_settings(BOOKMARKS_API_OWNER_ID=self.other.pk):
                self.assertEqual(self.client.get(self.record_url(attempt)).status_code, 404)
                self.assertEqual(self.client.get(reverse('demos:bookmarks:attempt_record', args=[attempt.pk])).status_code, 404)
            remote.assert_not_called()
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(self.record_url(attempt, 'other')).status_code, 404)
        with override_settings(BOOKMARKS_JOB_SERVICE_URL='https://changed.example.com/service'):
            response = self.client.get(self.record_url(attempt))
            self.assertContains(response, 'different job-service endpoint')

    def test_expired_and_pending_records_do_not_trigger_analysis_or_result_fetch(self):
        attempt = self.saved()
        remote = Mock()
        remote.job.return_value = {'job_id': ANALYSIS, 'status': 'running'}
        with patch('dwiest.django.demos.bookmarks.record_views.JobClient', return_value=remote):
            self.assertEqual(self.client.get(self.record_url(attempt, 'analysis')).status_code, 200)
        remote.job.assert_called_once_with(ANALYSIS)
        remote.job.side_effect = JobError('Job and artifact retention has expired.', 410)
        with patch('dwiest.django.demos.bookmarks.record_views.JobClient', return_value=remote):
            self.assertContains(self.client.get(self.record_url(attempt)), 'retention has expired')
        remote.submit.assert_not_called()

    def test_filterable_statuses_are_independent_and_keep_capture_author(self):
        first = self.saved()
        later = start(self.user, self.bookmark, self.original, URL, force_analysis=True, source_attempt=first)
        later.status = 'failed'; later.error = {'message': 'Provider failed'}; later.save()
        untouched = Bookmark.objects.create(owner=self.user, url='https://example.com/other', title='Untouched')
        with self.assertNumQueries(3):
            decorate([self.bookmark, untouched], self.user)
        self.assertEqual(self.bookmark.download_state, 'available')
        self.assertEqual(self.bookmark.analysis_state, 'failed')
        self.assertEqual(self.bookmark.article_author, 'John Doe')
        self.assertEqual(untouched.download_state, 'not_requested')
        home = reverse('demos:bookmarks:home')
        response = self.client.get(home, {'download_status': 'available', 'analysis_status': 'failed'})
        self.assertEqual([b.pk for b in response.context['page_obj']], [self.bookmark.pk])
        response = self.client.get(home, {'download_status': 'not_requested'})
        self.assertEqual([b.pk for b in response.context['page_obj']], [untouched.pk])
        self.assertFalse(Tag.objects.exists())
        self.assertEqual(self.client.get(home, {'download_status': 'invalid'}).context['page_obj'].paginator.count, 0)

    def test_detail_is_read_only_owner_bound_and_lists_saved_records(self):
        attempt = self.saved()
        url = reverse('demos:bookmarks:ui_detail', args=[self.bookmark.pk])
        before = self.bookmark.last_modified
        response = self.client.get(url)
        self.assertContains(response, 'author: John Doe')
        self.assertContains(response, self.record_url(attempt))
        self.bookmark.refresh_from_db(); self.assertEqual(self.bookmark.last_modified, before)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_url_changes_do_not_show_old_status_and_author(self):
        self.saved()
        self.bookmark.url = 'https://different.example.com/article'; self.bookmark.save()
        decorate([self.bookmark], self.user)
        self.assertEqual(self.bookmark.download_state, 'not_requested')
        self.assertEqual(self.bookmark.article_author, '')

    def test_review_same_url_once_sorted_tags_new_tag_approval_and_date_format(self):
        attempt = self.saved()
        review = attempt.review
        review.original['draft'].update(tags=['zebra', 'Alpha'], article_date='2026-11-17')
        review.proposal.update(tags=['zebra', 'New topic'], article_date='2026-11-17')
        review.save()
        url = reverse('demos:bookmarks:ai_review', args=[review.pk])
        page = self.client.get(url)
        self.assertTrue(page.context['same_url'])
        self.assertEqual(page.context['current_tags_text'], 'Alpha\nzebra')
        self.assertEqual(page.context['form'].initial['tags'], 'New topic\nzebra')
        self.assertNotIn('url', [row['name'] for row in page.context['rows']])
        self.assertContains(page, 'value="2026-11-17"')
        self.assertContains(page, 'data-tag-editor')
        self.assertContains(page, 'data-autosize')
        result = self.client.post(url, dict(PROPOSAL, url=URL, article_date='2026-11-17', tags='New topic\nPython', selected=['tags'], action='apply'))
        self.assertEqual(result.status_code, 302)
        self.assertEqual(set(Tag.objects.values_list('title', flat=True)), {'New topic', 'Python'})

    def test_different_direct_analysis_url_retains_explicit_comparison(self):
        attempt = self.saved(); review = attempt.review
        review.proposal['url'] = 'https://example.com/canonical'; review.save()
        response = self.client.get(reverse('demos:bookmarks:ai_review', args=[review.pk]))
        self.assertFalse(response.context['same_url'])
        self.assertIn('url', [row['name'] for row in response.context['rows']])
