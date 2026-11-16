import json
import io
import time
from datetime import timedelta
from unittest import mock
from urllib.error import HTTPError, URLError
from cryptography.fernet import Fernet
from django.core.management import call_command
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from .ai_credentials import AIError, AIArticleAccessError, SESSION_KEY, api_key_for, cipher, decrypt, encrypt
from .ai_forms import AIProposalForm, AISiteBlacklistForm
from .ai_sites import blacklisted_site, failed_site_offer, normalize_site
from ..bookmark_ai_models import BookmarkAISettings, BookmarkAIAnalysis, BookmarkAIAttempt
from .ai_service import APPLICATION_INSTRUCTIONS, analyze, openai_request
from .ai_views import apply_proposal, snapshot
from .models import Bookmark, Tag, BookmarkTag

KEY = Fernet.generate_key().decode()
API_KEY = 'sk-test-not-a-real-api-key'
URL = 'https://example.com/article'


def proposal(**changes):
    data = {'url': URL, 'title': 'Article title', 'description': 'A factual summary.', 'article_date': None, 'tags': ['AWS']}
    data.update(changes)
    return data


def response(*output, **kwargs):
    return dict({'id': 'resp_test', 'status': 'completed', 'output': list(output)}, **kwargs)


def call(name, output, arguments=None):
    return {'type': 'mcp_call', 'name': name, 'server_label': 'bookmarks', 'status': 'completed',
            'output': json.dumps(output), 'arguments': json.dumps(arguments or {})}


def analysis_response(bookmark_id=None, opened=True):
    fields = proposal(retrieved=True, failure_reason='')
    items = [call('get_bookmark' if bookmark_id else 'lookup_bookmark', {'exists': False}), call('list_tags', {'tags': []}),
             {'type': 'message', 'content': [{'type': 'output_text', 'text': json.dumps(fields), 'annotations': []}]}]
    if opened:
        items.insert(0, {'type': 'web_search_call', 'status': 'completed', 'action': {'type': 'open_page', 'url': URL}})
    return response(*items)


@override_settings(BOOKMARKS_AI_ENCRYPTION_KEYS=[KEY])
class BookmarkAITests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('demo', password='password')
        self.other = get_user_model().objects.create_user('other', password='password')
        self.owner_setting = override_settings(BOOKMARKS_API_OWNER_ID=self.user.pk)
        self.owner_setting.enable()
        self.addCleanup(self.owner_setting.disable)
        self.client.force_login(self.user)
        self.prefs = BookmarkAISettings.objects.create(owner=self.user, encrypted_api_key=encrypt(API_KEY))
        self.tag = Tag.objects.create(owner=self.user, title='AWS', style='')
        self.bookmark = Bookmark.objects.create(owner=self.user, url=URL, title='Original', description='Original text')
        BookmarkTag.objects.create(owner=self.user, bookmark=self.bookmark, tag=self.tag)
        self.settings_url = reverse('demos:bookmarks:ai_settings')
        self.editor_url = reverse('demos:bookmarks:bookmark')
        network_patch = mock.patch('dwiest.django.demos.bookmarks.ai_service.build_opener',
                                   side_effect=AssertionError('Unexpected network call'))
        self.no_network = network_patch.start()
        self.addCleanup(network_patch.stop)

    def review(self, bookmark=True, **values):
        original = snapshot(self.bookmark if bookmark else Bookmark(owner=self.user))
        return BookmarkAIAnalysis.objects.create(owner=self.user, bookmark_id=self.bookmark.pk if bookmark else None,
            original={'persisted': original, 'draft': dict(original)}, proposal=proposal(**values),
            sources=[{'url': URL, 'title': 'Article source'}], expires_at=timezone.now() + timedelta(minutes=30))

    def review_url(self, review):
        return reverse('demos:bookmarks:ai_review', args=[review.pk])

    def posted(self, **values):
        data = dict(proposal(), tags='AWS', selected=['url', 'title', 'description', 'article_date', 'tags'], action='apply')
        data['article_date'] = ''
        data.update(values)
        return data

    def test_article_failure_shows_reported_reason_timing_and_no_unnecessary_reads(self):
        fields = proposal(retrieved=False, failure_reason='The browsing tool reported HTTP 402 Payment Required.')
        failure = response({'type': 'web_search_call', 'status': 'completed', 'action': {'type': 'open_page', 'url': URL}},
                           {'type': 'message', 'content': [{'type': 'output_text', 'text': json.dumps(fields)}]})
        with mock.patch('dwiest.django.demos.bookmarks.ai_service.openai_request', return_value=failure) as api, \
                mock.patch('dwiest.django.demos.bookmarks.ai_service.time.monotonic', side_effect=[100.0, 115.0]):
            result = self.client.post(self.editor_url, {'url': URL, 'title': 'My draft', 'action': 'ai_analyze'})
        self.assertContains(result, 'OpenAI-reported reason:')
        self.assertContains(result, 'HTTP 402 Payment Required')
        self.assertContains(result, '15.0 seconds')
        self.assertContains(result, 'Publisher HTTP status and response headers were not provided')
        self.assertContains(result, 'Add this site to blacklist')
        self.assertEqual(result.context['ai_failure_details']['web_calls'], 1)
        self.assertEqual(result.context['ai_failure_details']['mcp_calls'], 0)
        self.assertEqual(result.context['form']['title'].value(), 'My draft')
        self.assertFalse(BookmarkAIAnalysis.objects.exists())
        api.assert_called_once()

    def test_verification_failures_are_distinct_from_reported_retrieval_failure(self):
        fields = proposal(retrieved=True, failure_reason='')
        cases = [
            ([], 'No page-open action was returned.'),
            ([{'type': 'web_search_call', 'status': 'completed', 'action': None}], 'No page-open action was returned.'),
            ([{'type': 'web_search_call', 'status': 'failed', 'action': {'type': 'open_page', 'url': URL}}], 'No page-open action completed.'),
            ([{'type': 'web_search_call', 'status': 'completed', 'action': {'type': 'open_page'}}], 'omitted its URL'),
            ([{'type': 'web_search_call', 'status': 'completed', 'action': {'type': 'open_page', 'url': URL + '/'}}], 'did not match the submitted article'),
        ]
        for web, evidence in cases:
            failure = response(*(web + [{'type': 'message', 'content': [{'type': 'output_text', 'text': json.dumps(fields)}]}]))
            with mock.patch('dwiest.django.demos.bookmarks.ai_service.openai_request', return_value=failure):
                with self.assertRaises(AIArticleAccessError) as caught:
                    analyze(self.user, API_KEY, self.prefs, URL)
            self.assertIn('reported reading the article', str(caught.exception))
            self.assertIn(evidence, caught.exception.details['verification'])
            self.assertEqual(caught.exception.details['reported_reason'], '')

    def test_reported_reason_is_bounded_redacted_and_html_escaped(self):
        from django.conf import settings
        token = settings.BOOKMARKS_AI_MCP_TOKEN
        reason = '<script>alert(1)</script> API ' + API_KEY + ' token ' + token + ' Bearer foreign-token-12345 '
        reason += 'detail ' * 300
        failure = response({'type': 'message', 'content': [{'type': 'output_text', 'text': json.dumps(proposal(retrieved=False, failure_reason=reason))}]})
        with mock.patch('dwiest.django.demos.bookmarks.ai_service.openai_request', return_value=failure):
            result = self.client.post(self.editor_url, {'url': URL, 'action': 'ai_analyze'})
        self.assertNotContains(result, API_KEY)
        self.assertNotContains(result, token)
        self.assertNotContains(result, 'foreign-token-12345')
        self.assertNotContains(result, '<script>alert(1)</script>')
        self.assertContains(result, '&lt;script&gt;alert(1)&lt;/script&gt;')
        self.assertLessEqual(len(result.context['ai_failure_details']['reported_reason']), 600)

    def test_failure_without_reason_does_not_invent_a_site_policy(self):
        failure = response({'type': 'message', 'content': [{'type': 'output_text', 'text': json.dumps(proposal(retrieved=False, failure_reason=''))}]})
        with mock.patch('dwiest.django.demos.bookmarks.ai_service.openai_request', return_value=failure):
            result = self.client.post(self.editor_url, {'url': URL, 'action': 'ai_analyze'})
        self.assertContains(result, 'OpenAI did not provide a specific reason.')
        self.assertContains(result, 'Site policy and payment requirements are unverified')
        self.assertNotIn('openai_http_status', result.context['ai_failure_details'])

    def test_provider_http_status_is_distinguished_from_publisher_status(self):
        error = HTTPError('https://api.openai.com/v1/responses', 429, 'provider-private-detail', {}, io.BytesIO(API_KEY.encode()))
        with mock.patch('dwiest.django.demos.bookmarks.ai_service.build_opener') as opener, \
                mock.patch('dwiest.django.demos.bookmarks.ai_service.time.monotonic', side_effect=[5.0, 8.0]):
            opener.return_value.open.side_effect = error
            result = self.client.post(self.editor_url, {'url': URL, 'action': 'ai_analyze'})
        self.assertContains(result, 'OpenAI API HTTP status:')
        self.assertContains(result, '3.0 seconds')
        self.assertEqual(result.context['ai_failure_details']['openai_http_status'], 429)
        self.assertNotContains(result, API_KEY)
        self.assertNotContains(result, 'provider-private-detail')
        self.assertNotContains(result, 'Add this site to blacklist')
        self.assertNotIn('article_failure', result.context['ai_failure_details'])
        opener.return_value.open.assert_called_once()

    def test_failed_article_offers_one_click_blacklist_without_saving_existing_draft(self):
        before = snapshot(self.bookmark)
        data = {'id': self.bookmark.pk, 'url': URL, 'title': 'Unsaved title',
                'description': 'Unsaved description', 'article_date': '2026-11-15',
                'status': '1', 'unread': 'on', 'tag_ids': [str(self.tag.pk)],
                'ai_instructions': 'Keep these instructions', 'next': '/bookmarks/?tag=1', 'action': 'ai_analyze'}
        with mock.patch('dwiest.django.demos.bookmarks.ai_service.openai_request', return_value=analysis_response(opened=False)) as api:
            failure = self.client.post(self.editor_url, data)
        api.assert_called_once()
        self.assertContains(failure, 'Add this site to blacklist')
        self.assertEqual(failure.context['ai_blacklist_offer']['domain'], 'example.com')
        token = failure.context['ai_blacklist_offer']['token']
        self.prefs.refresh_from_db()
        self.assertEqual(self.prefs.blocked_domains, [])
        original_key = self.prefs.encrypted_api_key
        data.update(action='ai_blacklist_site', ai_blacklist_offer=token)
        with mock.patch('dwiest.django.demos.bookmarks.ai_views.api_key_for') as key, \
                mock.patch('dwiest.django.demos.bookmarks.ai_service.mcp_connection_for') as mcp, \
                mock.patch('dwiest.django.demos.bookmarks.ai_service.openai_request') as api:
            for unused in range(2):
                result = self.client.post(self.editor_url, data)
                self.assertContains(result, 'are on your AI site blacklist')
                self.assertNotContains(result, 'Add this site to blacklist')
                form = result.context['form']
                for name in ['url', 'title', 'description', 'article_date', 'status']:
                    self.assertEqual(form[name].value(), data[name])
                self.assertEqual(form['tag_ids'].value(), data['tag_ids'])
                self.assertTrue(form['unread'].value())
                self.assertContains(result, 'Keep these instructions')
                self.assertEqual(result.context['next_url'], data['next'])
                self.assertIn('no-store', result['Cache-Control'])
            key.assert_not_called()
            mcp.assert_not_called()
            api.assert_not_called()
        self.prefs.refresh_from_db()
        self.bookmark.refresh_from_db()
        self.assertEqual(self.prefs.blocked_domains, ['example.com'])
        self.assertEqual(self.prefs.encrypted_api_key, original_key)
        self.assertEqual(snapshot(self.bookmark), before)
        self.assertFalse(BookmarkAIAnalysis.objects.exists())

    def test_quick_blacklist_preserves_new_draft_without_credentials_or_valid_bookmark_fields(self):
        data = {'url': 'https://www.new.example/article', 'title': '', 'description': 'My draft',
                'article_date': 'not-a-date', 'status': '-1', 'ai_instructions': 'Keep this',
                'action': 'ai_blacklist_site', 'ai_blacklist_offer': failed_site_offer(self.user, 'https://www.new.example/article')['token']}
        self.prefs.encrypted_api_key = ''
        self.prefs.save()
        count = Bookmark.objects.count()
        with override_settings(BOOKMARKS_AI_ENCRYPTION_KEYS=[], BOOKMARKS_AI_MCP_URL='', BOOKMARKS_AI_MODEL=''):
            result = self.client.post(self.editor_url, data)
        self.assertContains(result, 'new.example and its subdomains are on your AI site blacklist')
        self.assertEqual(result.context['form']['article_date'].value(), 'not-a-date')
        self.assertEqual(result.context['form']['description'].value(), 'My draft')
        self.assertEqual(Bookmark.objects.count(), count)
        self.no_network.assert_not_called()

    def test_custom_analysis_instructions_are_collapsed_and_preserved_after_failure(self):
        from html.parser import HTMLParser
        class Details(HTMLParser):
            instructions = None
            def handle_starttag(self, tag, attrs):
                values = dict(attrs)
                if tag == 'details' and 'data-ai-instructions' in values:
                    self.instructions = values
        with mock.patch('dwiest.django.demos.bookmarks.ai_service.analyze', side_effect=AIError('Article analysis failed')):
            failed = self.client.post(self.editor_url, {'url': URL, 'ai_instructions': 'Keep my custom instructions', 'action': 'ai_analyze'})
        for page in [self.client.get(self.editor_url), failed]:
            parser = Details()
            parser.feed(page.content.decode())
            self.assertIsNotNone(parser.instructions)
            self.assertNotIn('open', parser.instructions)
            self.assertContains(page, 'Custom analysis instructions (optional)')
        self.assertContains(page, 'Keep my custom instructions')

    def test_configuration_failures_do_not_offer_site_blacklisting(self):
        self.prefs.encrypted_api_key = ''
        self.prefs.save()
        result = self.client.post(self.editor_url, {'url': URL, 'action': 'ai_analyze'})
        self.assertContains(result, 'Enter an OpenAI API key')
        self.assertNotContains(result, 'Add this site to blacklist')
        self.assertNotIn('ai_blacklist_offer', result.context)

    def test_quick_blacklist_rejects_changed_url_forged_missing_and_expired_offers(self):
        token = failed_site_offer(self.user, URL)['token']
        data = {'id': self.bookmark.pk, 'url': URL, 'title': 'Never save this', 'status': '0', 'action': 'ai_blacklist_site'}
        before = snapshot(self.bookmark)
        for posted in [dict(data, ai_blacklist_offer=token, url='https://other.example/article'),
                       dict(data, ai_blacklist_offer=token + 'bad'), data]:
            result = self.client.post(self.editor_url, posted)
            self.assertContains(result, 'blacklist action expired or the article URL changed')
        with mock.patch('django.core.signing.time.time', return_value=time.time() + 1900):
            result = self.client.post(self.editor_url, dict(data, ai_blacklist_offer=token))
        self.assertContains(result, 'blacklist action expired or the article URL changed')
        self.prefs.refresh_from_db()
        self.bookmark.refresh_from_db()
        self.assertEqual(self.prefs.blocked_domains, [])
        self.assertEqual(snapshot(self.bookmark), before)
        self.no_network.assert_not_called()

    def test_quick_blacklist_requires_same_user_owner_permission_and_csrf(self):
        token = failed_site_offer(self.user, URL)['token']
        data = {'url': URL, 'title': 'Never save this', 'status': '0', 'action': 'ai_blacklist_site', 'ai_blacklist_offer': token}
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.assertEqual(client.post(self.editor_url, data).status_code, 403)
        self.client.force_login(self.other)
        result = self.client.post(self.editor_url, data)
        self.assertContains(result, 'configured demo account')
        with override_settings(BOOKMARKS_API_OWNER_ID=self.other.pk):
            result = self.client.post(self.editor_url, data)
        self.assertContains(result, 'blacklist action expired or the article URL changed')
        self.client.logout()
        self.client.post(self.editor_url, data)
        self.prefs.refresh_from_db()
        self.assertEqual(self.prefs.blocked_domains, [])
        self.assertFalse(BookmarkAISettings.objects.filter(owner=self.other).exists())
        self.assertEqual(Bookmark.objects.count(), 1)

    def test_quick_blacklist_preserves_other_rules_and_honors_limit(self):
        token = failed_site_offer(self.user, URL)['token']
        data = {'url': URL, 'action': 'ai_blacklist_site', 'ai_blacklist_offer': token}
        self.prefs.blocked_domains = ['site{}.example'.format(i) for i in range(100)]
        self.prefs.save()
        result = self.client.post(self.editor_url, data)
        self.assertContains(result, 'already contains 100 sites')
        self.prefs.refresh_from_db()
        self.assertEqual(len(self.prefs.blocked_domains), 100)
        self.prefs.blocked_domains = ['other.example']
        self.prefs.save()
        result = self.client.post(self.editor_url, data)
        self.assertContains(result, 'are on your AI site blacklist')
        self.prefs.refresh_from_db()
        self.assertEqual(self.prefs.blocked_domains, ['other.example', 'example.com'])
        self.assertEqual(blacklisted_site('https://news.example.com/new', self.prefs.blocked_domains), 'example.com')

    def test_blacklist_can_be_managed_without_ai_credentials_and_is_user_scoped(self):
        original_key = self.prefs.encrypted_api_key
        other_prefs = BookmarkAISettings.objects.create(owner=self.other, blocked_domains=['other.example'])
        with override_settings(BOOKMARKS_AI_ENCRYPTION_KEYS=[], BOOKMARKS_AI_MCP_URL=''):
            result = self.client.post(self.settings_url, {'action': 'save_blacklist',
                'blocked_domains': ' https://WWW.POLITICO.EU/article/test/ \npolitico.eu\nMSN.com.\n'})
        self.assertEqual(result.status_code, 302)
        self.prefs.refresh_from_db()
        other_prefs.refresh_from_db()
        self.assertEqual(self.prefs.blocked_domains, ['politico.eu', 'msn.com'])
        self.assertEqual(other_prefs.blocked_domains, ['other.example'])
        self.assertEqual(self.prefs.encrypted_api_key, original_key)
        self.assertEqual((self.prefs.instructions, self.prefs.model), ('', ''))
        page = self.client.get(self.settings_url)
        self.assertContains(page, 'politico.eu')
        self.assertContains(page, 'msn.com')
        result = self.client.post(self.settings_url, {'action': 'save_blacklist', 'blocked_domains': 'msn.com'})
        self.prefs.refresh_from_db()
        self.assertEqual(self.prefs.blocked_domains, ['msn.com'])
        self.client.post(self.settings_url, {'action': 'save_blacklist', 'blocked_domains': ''})
        self.prefs.refresh_from_db()
        self.assertEqual(self.prefs.blocked_domains, [])
        self.no_network.assert_not_called()

    def test_blacklist_invalid_entries_do_not_replace_saved_list(self):
        self.prefs.blocked_domains = ['example.com']
        self.prefs.save()
        for invalid in ['*.example.com', 'not a domain', 'https://user:password@example.com/path',
                        'ftp://example.com', 'example.com:invalid', 'example..com', '-bad.example', 'com', 'https://']:
            result = self.client.post(self.settings_url, {'action': 'save_blacklist', 'blocked_domains': invalid})
            self.assertEqual(result.status_code, 200)
            self.assertContains(result, 'Line 1:')
            self.prefs.refresh_from_db()
            self.assertEqual(self.prefs.blocked_domains, ['example.com'])
        form = AISiteBlacklistForm({'blocked_domains': '\n'.join('site{}.example'.format(i) for i in range(101))})
        self.assertFalse(form.is_valid())
        self.assertIn('Choose at most 100 sites.', form.errors['blocked_domains'])

    def test_blacklist_matching_normalization_and_domain_boundaries(self):
        self.assertEqual(normalize_site('https://WWW.Example.COM.:443/story?x=1#intro'), 'example.com')
        self.assertEqual(normalize_site('bücher.example'), 'xn--bcher-kva.example')
        for url in ['https://example.com/a', 'https://www.example.com/new', 'https://news.example.com/a',
                    'https://deep.news.example.com/a', 'http://EXAMPLE.COM.:8080/story']:
            self.assertEqual(blacklisted_site(url, ['example.com']), 'example.com')
        for url in ['https://notexample.com', 'https://example.com.evil.test', 'https://example.net',
                    'https://other.test/?next=example.com', 'https://other.test/example.com']:
            self.assertIsNone(blacklisted_site(url, ['example.com']))
        self.assertIsNone(blacklisted_site('https://example.com', ['news.example.com']))
        self.assertIsNone(blacklisted_site('https://[2001:db8::1]/', ['example.com']))
        self.assertEqual(blacklisted_site('https://www.bücher.example/story', ['xn--bcher-kva.example']), 'xn--bcher-kva.example')

    def test_blacklisted_site_warns_but_allows_explicit_analysis(self):
        self.prefs.blocked_domains = ['example.com']
        self.prefs.save()
        page = self.client.get(self.editor_url, {'id': self.bookmark.pk})
        self.assertContains(page, 'is on your AI site blacklist')
        self.assertContains(page, 'You can still use Analyze to retry.')
        with mock.patch('dwiest.django.demos.bookmarks.ai_service.openai_request', return_value=analysis_response(self.bookmark.pk)) as api:
            result = self.client.post(self.editor_url, {'id': self.bookmark.pk, 'url': URL, 'status': '0', 'action': 'ai_analyze'})
        self.assertEqual(result.status_code, 302)
        api.assert_called_once()
        self.assertTrue(BookmarkAIAttempt.objects.filter(owner=self.user, url=URL).exists())
        review_page = self.client.get(result.url)
        self.assertContains(review_page, 'Analysis is being attempted at your request')

    def test_attempt_time_persists_on_failure_and_updates_on_retry(self):
        original = snapshot(self.bookmark)
        data = {'id': self.bookmark.pk, 'url': URL, 'title': 'Draft', 'status': '0', 'action': 'ai_analyze'}
        before = timezone.now()
        with mock.patch('dwiest.django.demos.bookmarks.ai_service.openai_request', return_value=analysis_response(opened=False)):
            result = self.client.post(self.editor_url, data)
        attempt = BookmarkAIAttempt.objects.get(owner=self.user, url=URL)
        self.assertGreaterEqual(attempt.last_attempted_at, before)
        self.assertContains(result, 'Last analysis attempted for this URL:')
        self.assertContains(result, 'ago)')
        self.assertEqual(result.context['ai_last_attempt'].pk, attempt.pk)
        old_time = timezone.now() - timedelta(days=2)
        BookmarkAIAttempt.objects.filter(pk=attempt.pk).update(last_attempted_at=old_time)
        page = self.client.get(self.editor_url, {'id': self.bookmark.pk})
        self.assertEqual(page.context['ai_last_attempt'].last_attempted_at, old_time)
        with mock.patch('dwiest.django.demos.bookmarks.ai_service.openai_request', side_effect=AIError('Timed out')):
            result = self.client.post(self.editor_url, data)
        attempt.refresh_from_db()
        self.assertGreater(attempt.last_attempted_at, old_time)
        self.assertEqual(BookmarkAIAttempt.objects.filter(owner=self.user, url=URL).count(), 1)
        self.bookmark.refresh_from_db()
        self.assertEqual(snapshot(self.bookmark), original)
        self.assertFalse(BookmarkAIAnalysis.objects.exists())

    def test_attempt_times_are_user_and_url_scoped_and_not_written_by_other_actions(self):
        BookmarkAIAttempt.objects.create(owner=self.other, url=URL)
        self.assertNotContains(self.client.get(self.editor_url, {'id': self.bookmark.pk}), 'Last analysis attempted for this URL:')
        self.prefs.encrypted_api_key = ''
        self.prefs.save()
        result = self.client.post(self.editor_url, {'url': URL, 'action': 'ai_analyze'})
        self.assertContains(result, 'Enter an OpenAI API key')
        self.assertFalse(BookmarkAIAttempt.objects.filter(owner=self.user).exists())
        self.client.post(self.editor_url, {'url': 'https://example.com/manual', 'title': 'Manual', 'status': '0'})
        self.assertFalse(BookmarkAIAttempt.objects.filter(owner=self.user).exists())
        self.client.post(self.editor_url, {'url': URL, 'action': 'ai_blacklist_site', 'ai_blacklist_offer': failed_site_offer(self.user, URL)['token']})
        self.assertFalse(BookmarkAIAttempt.objects.filter(owner=self.user).exists())

    def test_unblocked_analysis_runs_again_after_removing_domain(self):
        self.prefs.blocked_domains = ['example.com']
        self.prefs.save()
        self.client.post(self.settings_url, {'action': 'save_blacklist', 'blocked_domains': ''})
        with mock.patch('dwiest.django.demos.bookmarks.ai_service.analyze', return_value=(proposal(), [])) as api:
            result = self.client.post(self.editor_url, {'url': 'https://example.com/new', 'title': 'Draft', 'status': '0', 'action': 'ai_analyze'})
        self.assertEqual(result.status_code, 302)
        api.assert_called_once()
        self.assertEqual(api.call_args[0][2].blocked_domains, [])

    def test_blacklist_does_not_block_manual_save_or_approved_proposal(self):
        self.prefs.blocked_domains = ['example.com']
        self.prefs.save()
        result = self.client.post(self.editor_url, {'id': self.bookmark.pk, 'url': URL, 'title': 'Manual title', 'status': '0'})
        self.assertEqual(result.status_code, 302)
        self.bookmark.refresh_from_db()
        review = self.review()
        result = self.client.post(self.review_url(review), self.posted(selected=['title'], title='Approved title'))
        self.assertEqual(result.status_code, 302)
        self.bookmark.refresh_from_db()
        self.assertEqual(self.bookmark.title, 'Approved title')
        self.no_network.assert_not_called()

    def test_blacklist_management_requires_owner_and_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.assertEqual(client.post(self.settings_url, {'action': 'save_blacklist', 'blocked_domains': 'example.com'}).status_code, 403)
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(self.settings_url, {'action': 'save_blacklist', 'blocked_domains': 'example.com'}).status_code, 403)
        self.prefs.refresh_from_db()
        self.assertEqual(self.prefs.blocked_domains, [])

    def test_other_ai_settings_actions_preserve_blacklist(self):
        self.prefs.blocked_domains = ['example.com']
        self.prefs.save()
        for data in [{'action': 'save', 'storage': 'session', 'instructions': 'Test'},
                     {'action': 'reset'}, {'action': 'remove'}]:
            self.client.post(self.settings_url, data)
            self.prefs.refresh_from_db()
            self.assertEqual(self.prefs.blocked_domains, ['example.com'])

    def test_settings_saved_key_encrypted_never_rendered_and_password_independent(self):
        result = self.client.get(self.settings_url)
        self.assertEqual(result.status_code, 200)
        self.assertNotContains(result, API_KEY)
        self.assertIn('no-store', result['Cache-Control'])
        self.user.set_password('a-new-password')
        self.user.save()
        self.assertEqual(decrypt(self.prefs.encrypted_api_key), API_KEY)
        self.assertNotIn(API_KEY, self.prefs.encrypted_api_key)

    def test_save_session_only_and_remove(self):
        result = self.client.post(self.settings_url, {'api_key': API_KEY, 'storage': 'session', 'instructions': 'Use technical tags.'})
        self.assertEqual(result.status_code, 302)
        value = self.client.session[SESSION_KEY]
        self.assertNotEqual(value, API_KEY)
        self.assertEqual(decrypt(value), API_KEY)
        self.assertTrue(self.client.session.get_expire_at_browser_close())
        self.client.post(self.settings_url, {'action': 'remove'})
        self.prefs.refresh_from_db()
        self.assertEqual(self.prefs.encrypted_api_key, '')
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_session_cookies_and_missing_encryption_are_rejected(self):
        with override_settings(SESSION_ENGINE='django.contrib.sessions.backends.signed_cookies'):
            client = Client()
            client.force_login(self.user)
            result = client.post(self.settings_url, {'api_key': API_KEY, 'storage': 'session'})
            self.assertContains(result, 'require server-side Django sessions')
            self.assertNotContains(result, API_KEY)
        with override_settings(BOOKMARKS_AI_ENCRYPTION_KEYS=[]):
            result = self.client.post(self.settings_url, {'api_key': API_KEY, 'storage': 'saved'})
            self.assertContains(result, 'Configure the separate AI encryption key')
            self.assertNotContains(result, API_KEY)

    def test_connection_test_does_not_store_submitted_key(self):
        with mock.patch('dwiest.django.demos.bookmarks.ai_service.openai_request', return_value={}) as api:
            result = self.client.post(self.settings_url, {'action': 'test', 'api_key': 'sk-another-key', 'storage': 'session'})
        self.assertEqual(result.status_code, 200)
        self.assertNotContains(result, 'sk-another-key')
        api.assert_called_once_with('sk-another-key', model=True)
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_wrong_owner_login_and_review_ownership(self):
        review = self.review()
        self.client.logout()
        self.assertEqual(self.client.get(self.settings_url).status_code, 302)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(self.settings_url).status_code, 403)
        self.assertEqual(self.client.get(self.review_url(review)).status_code, 403)
        with override_settings(BOOKMARKS_API_OWNER_ID=self.other.pk):
            self.assertEqual(self.client.get(self.review_url(review)).status_code, 404)

    def test_csrf_is_required_for_credentials_and_approval(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.assertEqual(client.post(self.settings_url, {'action': 'remove'}).status_code, 403)
        self.assertEqual(client.post(self.review_url(self.review()), self.posted()).status_code, 403)

    def test_analysis_uses_read_only_mcp_and_actual_article_evidence(self):
        with mock.patch('dwiest.django.demos.bookmarks.ai_service.openai_request', return_value=analysis_response()) as api:
            result, sources = analyze(self.user, API_KEY, self.prefs, URL, task_instructions='Focus on architecture.')
        self.assertEqual(result, proposal())
        self.assertEqual(sources[0]['url'], URL)
        payload = api.call_args[0][1]
        self.assertFalse(payload['store'])
        mcp = payload['tools'][1]
        self.assertEqual(mcp['require_approval'], 'never')
        self.assertTrue(all(name not in mcp['allowed_tools'] for name in ['create_tag', 'create_bookmark', 'update_bookmark', 'delete_bookmark']))
        self.assertIn('Focus on architecture.', payload['input'])
        self.assertEqual(payload['instructions'], APPLICATION_INSTRUCTIONS)

    def test_snippets_mcp_failure_and_missing_checks_are_not_accepted(self):
        for result in [analysis_response(opened=False), response(call('list_tags', {'isError': True})),
                       response({'type': 'mcp_approval_request'})]:
            with mock.patch('dwiest.django.demos.bookmarks.ai_service.openai_request', return_value=result):
                with self.assertRaises(AIError):
                    analyze(self.user, API_KEY, self.prefs, URL)

    def test_analyze_editor_creates_review_without_database_writes(self):
        before = (Bookmark.objects.count(), Tag.objects.count())
        with mock.patch('dwiest.django.demos.bookmarks.ai_service.analyze', return_value=(proposal(), [{'url': URL, 'title': 'Source'}])):
            result = self.client.post(self.editor_url, {'id': self.bookmark.pk, 'url': URL, 'title': 'Draft title', 'status': '0', 'tag_ids': [self.tag.pk], 'action': 'ai_analyze'})
        self.assertEqual(result.status_code, 302)
        review = BookmarkAIAnalysis.objects.get()
        self.assertEqual(review.original['draft']['title'], 'Draft title')
        self.bookmark.refresh_from_db()
        self.assertEqual(self.bookmark.title, 'Original')
        self.assertEqual(before, (Bookmark.objects.count(), Tag.objects.count()))
        page = self.client.get(result.url)
        self.assertContains(page, 'Approve and apply changes')

    def test_missing_configuration_leaves_regular_save_working(self):
        with override_settings(BOOKMARKS_AI_MCP_URL=''):
            result = self.client.post(self.editor_url, {'id': self.bookmark.pk, 'url': URL, 'title': 'Original', 'status': '0', 'action': 'ai_analyze'})
            self.assertContains(result, 'Configure the HTTPS MCP endpoint')
            result = self.client.post(self.editor_url, {'id': self.bookmark.pk, 'url': URL, 'title': 'Manual title', 'status': '0'})
        self.assertEqual(result.status_code, 302)
        self.bookmark.refresh_from_db()
        self.assertEqual(self.bookmark.title, 'Manual title')

    def test_edited_approval_and_unselected_field_are_exact(self):
        review = self.review()
        result = self.client.post(self.review_url(review), self.posted(title='My reviewed title', description='Do not apply this', selected=['title']))
        self.assertEqual(result.status_code, 302)
        self.bookmark.refresh_from_db()
        self.assertEqual(self.bookmark.title, 'My reviewed title')
        self.assertEqual(self.bookmark.description, 'Original text')
        self.assertEqual(list(self.bookmark.tags()), [self.tag])
        review.refresh_from_db()
        self.assertEqual(review.status, 'applied')
        self.assertEqual(review.approved['title'], 'My reviewed title')
        self.assertEqual(review.approved['description'], 'Original text')
        self.no_network.assert_not_called()

    def test_new_bookmark_and_tags_created_only_after_approval(self):
        other_tag = Tag.objects.create(owner=self.other, title='Django', style='')
        review = self.review(bookmark=False, url='https://example.com/new')
        review.original['draft'].update(status=1, unread=True)
        review.save()
        before = Bookmark.objects.count()
        self.client.get(self.review_url(review))
        self.assertEqual(Bookmark.objects.count(), before)
        result = self.client.post(self.review_url(review), self.posted(url='https://example.com/new', tags='aws\nDjango', article_date='2026-11-15'))
        self.assertEqual(result.status_code, 302)
        review.refresh_from_db()
        saved = Bookmark.objects.get(pk=review.bookmark_id, owner=self.user)
        self.assertEqual(saved.article_date.strftime('%Y-%m-%d'), '2026-11-15')
        self.assertEqual((saved.status, saved.unread), (1, True))
        tags = list(BookmarkTag.objects.filter(bookmark=saved))
        self.assertEqual(len(tags), 2)
        self.assertIn(self.tag.pk, [link.tag_id for link in tags])
        self.assertNotIn(other_tag.pk, [link.tag_id for link in tags])
        self.assertTrue(all(link.owner_id == self.user.pk and link.tag.owner_id == self.user.pk for link in tags))
        self.assertEqual(review.status, 'applied')
        self.assertEqual(review.results, [])
        self.no_network.assert_not_called()

    def test_existing_bookmark_new_tags_and_clearing_tags(self):
        review = self.review()
        result = self.client.post(self.review_url(review), self.posted(tags='AWS\nDjango'))
        self.assertEqual(result.status_code, 302)
        self.assertEqual({t.title for t in self.bookmark.tags()}, {'AWS', 'Django'})
        self.bookmark.refresh_from_db()
        review = self.review()
        result = self.client.post(self.review_url(review), self.posted(tags=''))
        self.assertEqual(result.status_code, 302)
        self.assertFalse(BookmarkTag.objects.filter(bookmark=self.bookmark).exists())
        self.assertTrue(Tag.objects.filter(owner=self.user, title='Django').exists())
        self.no_network.assert_not_called()

    def test_cancellation_expiry_stale_data_and_handled_review_never_write(self):
        for state in ['cancel', 'expired', 'stale', 'duplicate']:
            review = self.review()
            if state == 'expired':
                review.expires_at = timezone.now() - timedelta(seconds=1)
                review.save()
            if state == 'stale':
                self.bookmark.title = 'Changed elsewhere'
                self.bookmark.save()
            if state == 'duplicate':
                review.status = 'applying'
                review.save()
            before = snapshot(self.bookmark)
            self.client.post(self.review_url(review), self.posted(action='cancel' if state == 'cancel' else 'apply', tags='Should not exist'))
            self.bookmark.refresh_from_db()
            self.assertEqual(snapshot(self.bookmark), before)
            self.assertFalse(Tag.objects.filter(title='Should not exist').exists())
        self.no_network.assert_not_called()

    def test_database_failure_rolls_back_tags_bookmark_and_review_then_allows_retry(self):
        review = self.review()
        before = snapshot(self.bookmark)
        real_create = BookmarkTag.objects.get_or_create
        def fail_after_assignment(*args, **kwargs):
            real_create(*args, **kwargs)
            raise RuntimeError('Injected failure after assignment')
        with mock.patch.object(BookmarkTag.objects, 'get_or_create', side_effect=fail_after_assignment):
            result = self.client.post(self.review_url(review), self.posted(tags='NewTag'))
        self.assertContains(result, 'No changes were saved')
        review.refresh_from_db()
        self.bookmark.refresh_from_db()
        self.assertEqual(review.status, 'pending')
        self.assertEqual(review.approved, {})
        self.assertEqual(snapshot(self.bookmark), before)
        self.assertFalse(Tag.objects.filter(owner=self.user, title='NewTag').exists())
        again = self.client.post(self.review_url(review), self.posted(tags='NewTag'))
        self.assertEqual(again.status_code, 302)
        self.assertEqual({t.title for t in self.bookmark.tags()}, {'NewTag'})

    def test_review_completion_failure_rolls_back_new_bookmark(self):
        review = self.review(bookmark=False, url='https://example.com/new')
        with mock.patch.object(BookmarkAIAnalysis, 'save', side_effect=RuntimeError('Injected completion failure')):
            result = self.client.post(self.review_url(review), self.posted(url='https://example.com/new', tags='NewTag'))
        self.assertContains(result, 'No changes were saved')
        self.assertFalse(Bookmark.objects.filter(url='https://example.com/new').exists())
        self.assertFalse(Tag.objects.filter(title='NewTag').exists())
        review.refresh_from_db()
        self.assertEqual(review.status, 'pending')
        self.assertIsNone(review.bookmark_id)

    def test_global_url_duplicate_is_rejected_without_writes(self):
        Bookmark.objects.create(owner=self.other, url='https://example.com/taken', title='Other')
        review = self.review()
        result = self.client.post(self.review_url(review), self.posted(url='https://example.com/taken', tags='NewTag'))
        self.assertContains(result, 'That URL already exists')
        self.bookmark.refresh_from_db()
        review.refresh_from_db()
        self.assertEqual(self.bookmark.url, URL)
        self.assertEqual(review.status, 'pending')
        self.assertFalse(Tag.objects.filter(title='NewTag').exists())

    def test_repeated_approval_and_stale_in_memory_review_cannot_execute_twice(self):
        review = self.review(bookmark=False, url='https://example.com/new')
        stale = BookmarkAIAnalysis.objects.get(pk=review.pk)
        result = self.client.post(self.review_url(review), self.posted(url='https://example.com/new', tags='NewTag'))
        self.assertEqual(result.status_code, 302)
        again = self.client.post(self.review_url(review), self.posted(url='https://example.com/new', tags='NewTag'))
        self.assertContains(again, 'already been handled')
        request = mock.Mock(user=self.user)
        with self.assertRaisesRegex(AIError, 'already been handled'):
            apply_proposal(request, stale, dict(proposal(url='https://example.com/new'), status=0, unread=False))
        self.assertEqual(Bookmark.objects.filter(url='https://example.com/new').count(), 1)
        self.assertEqual(Tag.objects.filter(owner=self.user, title='NewTag').count(), 1)

    def test_changed_tag_assignment_invalidates_review(self):
        review = self.review()
        BookmarkTag.objects.filter(bookmark=self.bookmark).delete()
        result = self.client.post(self.review_url(review), self.posted(tags='NewTag'))
        self.assertContains(result, 'changed after analysis')
        self.assertFalse(Tag.objects.filter(title='NewTag').exists())
        self.assertFalse(BookmarkTag.objects.filter(bookmark=self.bookmark).exists())

    def test_unchanged_publication_timestamp_is_preserved(self):
        self.bookmark.article_date = timezone.now()
        self.bookmark.save()
        timestamp = self.bookmark.article_date
        review = self.review()
        result = self.client.post(self.review_url(review), self.posted(selected=['title'], title='Reviewed'))
        self.assertEqual(result.status_code, 302)
        self.bookmark.refresh_from_db()
        self.assertEqual(self.bookmark.article_date, timestamp)

    def test_approval_needs_no_ai_key_encryption_secret_model_or_mcp(self):
        review = self.review()
        self.prefs.encrypted_api_key = ''
        self.prefs.save()
        with override_settings(BOOKMARKS_AI_ENCRYPTION_KEYS=[], BOOKMARKS_AI_MCP_URL='', BOOKMARKS_AI_MCP_TOKEN='',
                               BOOKMARKS_AI_MCP_SECRET_ID='', BOOKMARKS_AI_ENCRYPTION_SECRET_ID='', BOOKMARKS_AI_MODEL=''):
            result = self.client.post(self.review_url(review), self.posted(selected=['title'], title='Reviewed title'))
        self.assertEqual(result.status_code, 302)
        self.bookmark.refresh_from_db()
        self.assertEqual(self.bookmark.title, 'Reviewed title')
        page = self.client.get(result.url)
        self.assertContains(page, 'Approved bookmark saved.')
        self.assertNotContains(page, 'saved through MCP')
        self.no_network.assert_not_called()

    def test_rotation_retains_old_decryption_then_retires_old_key(self):
        old = self.prefs.encrypted_api_key
        new = Fernet.generate_key().decode()
        with override_settings(BOOKMARKS_AI_ENCRYPTION_KEYS=[new, KEY]):
            self.assertEqual(decrypt(old), API_KEY)
            rotated = cipher().rotate(old.encode()).decode()
        with override_settings(BOOKMARKS_AI_ENCRYPTION_KEYS=[new]):
            self.assertEqual(decrypt(rotated), API_KEY)
            with self.assertRaises(AIError):
                decrypt(old)

    def test_rotation_command_and_review_cleanup(self):
        old = self.prefs.encrypted_api_key
        new = Fernet.generate_key().decode()
        with override_settings(BOOKMARKS_AI_ENCRYPTION_KEYS=[new, KEY]):
            call_command('rotate_bookmark_ai_keys', '--dry-run', stdout=io.StringIO())
            self.prefs.refresh_from_db()
            self.assertEqual(self.prefs.encrypted_api_key, old)
            call_command('rotate_bookmark_ai_keys', stdout=io.StringIO())
        self.prefs.refresh_from_db()
        with override_settings(BOOKMARKS_AI_ENCRYPTION_KEYS=[new]):
            self.assertEqual(decrypt(self.prefs.encrypted_api_key), API_KEY)
        recent = self.review()
        expired = self.review()
        expired.expires_at = timezone.now() - timedelta(days=8)
        expired.save()
        call_command('cleanup_bookmark_ai', stdout=io.StringIO())
        self.assertTrue(BookmarkAIAnalysis.objects.filter(pk=recent.pk).exists())
        self.assertFalse(BookmarkAIAnalysis.objects.filter(pk=expired.pk).exists())

    def test_provider_errors_do_not_expose_bodies_or_credentials(self):
        for error in [HTTPError('https://api.openai.com', 401, 'private-provider-detail', {}, io.BytesIO(API_KEY.encode())),
                      HTTPError('https://api.openai.com', 429, 'private-provider-detail', {}, io.BytesIO(API_KEY.encode())),
                      URLError('private-provider-detail')]:
            with mock.patch('dwiest.django.demos.bookmarks.ai_service.build_opener') as opener:
                opener.return_value.open.side_effect = error
                with self.assertRaises(AIError) as raised:
                    openai_request(API_KEY, {'model': 'test-model'})
            self.assertNotIn(API_KEY, str(raised.exception))
            self.assertNotIn('private-provider-detail', str(raised.exception))

