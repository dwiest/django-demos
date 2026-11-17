from unittest.mock import Mock, patch
from django.test import TestCase, override_settings
from django.urls import reverse
from . import test_enrichment as fixtures
from .test_enrichment import BASE, URL, RETRIEVAL, ANALYSIS, PROPOSAL
from .enrichment import start, advance
from .ai_views import snapshot
from .models import Bookmark
from ..bookmark_ai_models import BookmarkEnrichmentAttempt, BookmarkAIAnalysis


@override_settings(BOOKMARKS_JOB_SERVICE_URL=BASE, BOOKMARKS_JOB_SERVICE_REGION='us-east-1')
class RetryReviewHistoryTests(TestCase):
    setUp = fixtures.EnrichmentTests.setUp
    complete = fixtures.EnrichmentTests.complete

    def saved(self):
        return self.complete(start(self.user, self.bookmark, self.original, URL, instructions='Original instructions.'))[0]

    def attempt_url(self, a):
        return reverse('demos:bookmarks:enrichment', args=[a.pk])

    def editor(self):
        return reverse('demos:bookmarks:bookmark')+'?id='+str(self.bookmark.pk)

    def history(self, bookmark=None):
        return reverse('demos:bookmarks:enrichment_history')+('?bookmark='+str(bookmark.pk) if bookmark else '')

    def payload(self, action, token, **extra):
        return dict(id=str(self.bookmark.pk), url=URL, title=self.bookmark.title,
            description=self.bookmark.description, article_date='', status='0', action=action, ai_retry_token=token, **extra)

    def test_attempt_shows_original_instructions_and_validated_editable_form(self):
        a = self.saved()
        page = self.client.get(self.attempt_url(a))
        self.assertContains(page, 'Custom instructions used for this attempt')
        self.assertEqual(page.context['retry_form']['instructions'].value(), 'Original instructions.')
        response = self.client.post(self.attempt_url(a), {'action':'retry_analysis', 'instructions':'x'*4001})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['retry_form'].errors)
        self.assertEqual(BookmarkEnrichmentAttempt.objects.count(), 1)

    def test_edited_and_cleared_instructions_create_distinct_safe_retries(self):
        a = self.saved()
        urls = []
        for value in ['New instructions.', '']:
            response = self.client.post(self.attempt_url(a), {'action':'retry_analysis', 'instructions':value})
            urls.append(response.url)
            retry = BookmarkEnrichmentAttempt.objects.exclude(pk=a.pk).latest('created_at')
            self.assertEqual(retry.request_options.get('instructions', ''), value)
            self.assertEqual(retry.retrieval_job_id, RETRIEVAL)
            self.assertFalse(retry.request_options.get('auto_apply'))
            remote=Mock();remote.submit.return_value={'job_id':ANALYSIS}
            with patch('dwiest.django.demos.bookmarks.enrichment.JobClient', return_value=remote):
                advance(retry.pk)
            self.assertEqual(remote.submit.call_args[0][0]['request'].get('instructions',''),value)
        self.assertNotEqual(*urls)
        a.refresh_from_db();self.assertEqual(a.request_options['instructions'],'Original instructions.')

    def test_retry_rebases_on_current_values_after_approval_without_saving_bookmark(self):
        a = self.saved()
        self.bookmark.title = 'Approved title'; self.bookmark.save()
        response = self.client.post(self.attempt_url(a), {'action':'retry_analysis','instructions':'New focus'})
        self.assertEqual(response.status_code,302)
        retry=BookmarkEnrichmentAttempt.objects.exclude(pk=a.pk).get()
        self.assertEqual(retry.original['persisted'],snapshot(self.bookmark))
        self.assertEqual(retry.original['draft']['title'],'Approved title')
        self.bookmark.refresh_from_db();self.assertEqual(self.bookmark.title,'Approved title')
        self.bookmark.url='https://changed.example.com/';self.bookmark.save()
        self.client.post(self.attempt_url(a), {'action':'retry_analysis'})
        self.assertEqual(BookmarkEnrichmentAttempt.objects.count(),2)

    def test_editor_labels_instructions_and_explicit_retries_are_idempotent(self):
        self.assertContains(self.client.get(self.editor()), 'Download page')
        self.assertContains(self.client.get(self.editor()), '>Analyze</button>')
        a = self.saved()
        page=self.client.get(self.editor());token=page.context['ai_retry_token']
        self.assertContains(page,'Retry Download');self.assertContains(page,'Retry Analysis')
        self.assertEqual(page.context['ai_instructions'],'Original instructions.')
        data=self.payload('job_retry_analysis',token,ai_instructions='Updated in editor')
        first=self.client.post(reverse('demos:bookmarks:bookmark'),data)
        second=self.client.post(reverse('demos:bookmarks:bookmark'),data)
        self.assertEqual(first.url,second.url)
        retry=BookmarkEnrichmentAttempt.objects.exclude(pk=a.pk).get()
        self.assertEqual(retry.status,'analysis_pending')
        self.assertEqual(retry.retrieval_job_id,RETRIEVAL)
        self.assertEqual(retry.request_options['instructions'],'Updated in editor')
        token=self.client.get(self.editor()).context['ai_retry_token']
        self.client.post(reverse('demos:bookmarks:bookmark'),self.payload('job_retry_download',token,ai_instructions='Download again'))
        refreshed=BookmarkEnrichmentAttempt.objects.filter(mode='download').get()
        self.assertTrue(refreshed.request_options['force_refresh'])
        self.assertEqual(refreshed.status,'retrieval_pending')

    def test_retry_token_and_saved_capture_are_bound_to_owner_bookmark_and_url(self):
        a = self.saved()
        token=self.client.get(self.editor()).context['ai_retry_token']
        invalid=self.payload('job_retry_analysis',token+'tampered',ai_instructions='')
        page=self.client.post(reverse('demos:bookmarks:bookmark'),invalid)
        self.assertContains(page,'retry form expired or is invalid')
        changed=self.payload('job_retry_analysis',token,ai_instructions='')
        changed['url']='https://different.example.com/'
        self.assertContains(self.client.post(reverse('demos:bookmarks:bookmark'),changed),'No readable saved download')
        self.client.force_login(self.other)
        with override_settings(BOOKMARKS_API_OWNER_ID=self.other.pk):
            self.assertEqual(self.client.post(self.attempt_url(a),{'action':'retry_analysis','instructions':'Stolen'}).status_code,404)
        self.assertEqual(BookmarkEnrichmentAttempt.objects.count(),1)

    def test_applied_review_shows_saved_approved_and_original_values_read_only(self):
        a=self.saved(); review=a.review
        review.status='applied';review.approved=dict(review.proposal,title='Approved custom title',tags=['Zebra','Alpha']);review.save()
        self.bookmark.title='Later manual edit';self.bookmark.save()
        url=reverse('demos:bookmarks:ai_review',args=[review.pk])
        page=self.client.get(url)
        self.assertContains(page,'Applied bookmark values');self.assertContains(page,'Approved custom title')
        self.assertContains(page,'Original AI proposal');self.assertContains(page,PROPOSAL['title'])
        self.assertNotContains(page,'name="selected"');self.assertNotContains(page,'data-ai-apply')
        self.assertNotContains(page,'Later manual edit')
        attempt_page=self.client.get(self.attempt_url(a))
        self.assertContains(attempt_page,'View applied proposal')
        self.assertNotContains(attempt_page,'Review saved proposal')
        self.assertContains(attempt_page,url)
        self.client.post(url,dict(PROPOSAL,url=URL,article_date='',tags='Injected',selected=['title'],action='apply'))
        self.bookmark.refresh_from_db();self.assertEqual(self.bookmark.title,'Later manual edit')

    def failed(self, bookmark, number):
        return BookmarkEnrichmentAttempt.objects.create(owner=self.user,bookmark_id=bookmark.pk,url=bookmark.url,
            service_url=BASE,fingerprint='failed-'+str(number),status='failed')

    def test_bookmark_history_pagination_cleanup_and_redirect_stay_scoped(self):
        other=Bookmark.objects.create(owner=self.user,url='https://example.com/other',title='Other bookmark')
        for i in range(26):self.failed(self.bookmark,i)
        other_attempt=self.failed(other,99)
        history=self.history(self.bookmark)
        first=self.client.get(history)
        self.assertEqual(first.context['page_obj'].paginator.count,26)
        self.assertNotContains(first,'Other bookmark');self.assertContains(first,'bookmark='+str(self.bookmark.pk))
        second=self.client.get(history+'&page=2');self.assertEqual(len(second.context['page_obj']),1)
        preview=self.client.post(history,{'action':'preview_failed','bookmark':str(self.bookmark.pk)})
        self.assertEqual(preview.context['confirmation']['count'],26)
        self.assertContains(preview,'action="'+history+'"');self.assertContains(preview,'href="'+history+'">Cancel')
        token=preview.context['confirmation']['token']
        result=self.client.post(history,{'action':'confirm','bookmark':str(self.bookmark.pk),'token':token})
        self.assertEqual(result.url,history)
        self.assertTrue(BookmarkEnrichmentAttempt.objects.filter(pk=other_attempt.pk).exists())
        self.assertEqual(self.client.get(self.history()).context['page_obj'].paginator.count,1)

    def test_history_confirmation_cannot_broaden_or_switch_bookmark_scope(self):
        other=Bookmark.objects.create(owner=self.user,url='https://example.com/other',title='Other')
        self.failed(self.bookmark,1);self.failed(other,2)
        scoped=self.history(self.bookmark)
        token=self.client.post(scoped,{'action':'preview_failed'}).context['confirmation']['token']
        self.client.post(self.history(),{'action':'confirm','token':token})
        self.client.post(self.history(other),{'action':'confirm','token':token})
        self.assertEqual(BookmarkEnrichmentAttempt.objects.count(),2)
        for value in ['invalid','999999','99999999999999999999999999999999999999']:
            self.assertEqual(self.client.get(self.history()+'?bookmark='+value).status_code,404)
        owned_by_other=Bookmark.objects.create(owner=self.other,url='https://private.example.com/',title='Private')
        self.assertEqual(self.client.get(self.history(owned_by_other)).status_code,404)
