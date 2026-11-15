import json
import io
from datetime import timedelta
from unittest import mock
from urllib.error import HTTPError, URLError
from cryptography.fernet import Fernet
from django.core.management import call_command
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from .ai_credentials import AIError, SESSION_KEY, api_key_for, cipher, decrypt, encrypt
from .ai_forms import AIProposalForm
from ..bookmark_ai_models import BookmarkAISettings, BookmarkAIAnalysis
from .ai_service import APPLICATION_INSTRUCTIONS, analyze, execute_call, openai_request
from .ai_views import snapshot
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

    def fake_write(self, user, key, prefs, name, arguments, before_approve=None):
        self.assertEqual(user, self.user)
        self.assertEqual(key, API_KEY)
        if before_approve:
            before_approve()
        if name == 'create_tag':
            tag = Tag.objects.create(owner=user, **arguments)
            return {'id': tag.pk}
        if name == 'create_bookmark':
            values = {k: v for k, v in arguments.items() if k not in ('tags', 'compact')}
            saved = Bookmark.objects.create(owner=user, **values)
            for title in arguments['tags']:
                tag, _ = Tag.objects.get_or_create(owner=user, title=title, defaults={'style': ''})
                BookmarkTag.objects.create(owner=user, bookmark=saved, tag=tag)
        else:
            saved = Bookmark.objects.get(owner=user, pk=arguments['bookmark_id'])
            changes = dict(arguments['changes'])
            tag_ids = changes.pop('tag_ids', None)
            for name, value in changes.items():
                setattr(saved, name, value)
            saved.save()
            if tag_ids is not None:
                BookmarkTag.objects.filter(owner=user, bookmark=saved).delete()
                for tag_id in tag_ids:
                    BookmarkTag.objects.create(owner=user, bookmark=saved, tag_id=tag_id)
        return {'id': saved.pk}

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
        with mock.patch('dwiest.django.demos.bookmarks.ai_service.execute_call', side_effect=self.fake_write) as write:
            result = self.client.post(self.review_url(review), self.posted(title='My reviewed title', description='Do not apply this', selected=['title']))
        self.assertEqual(result.status_code, 302)
        write.assert_called_once()
        self.assertEqual(write.call_args[0][4], {'bookmark_id': self.bookmark.pk, 'changes': {'title': 'My reviewed title'}})
        self.bookmark.refresh_from_db()
        self.assertEqual(self.bookmark.description, 'Original text')
        review.refresh_from_db()
        self.assertEqual(review.status, 'applied')

    def test_new_bookmark_and_tags_created_only_after_approval(self):
        review = self.review(bookmark=False, url='https://example.com/new')
        with mock.patch('dwiest.django.demos.bookmarks.ai_service.execute_call', side_effect=self.fake_write) as write:
            result = self.client.post(self.review_url(review), self.posted(url='https://example.com/new', tags='AWS\nDjango'))
        self.assertEqual(result.status_code, 302)
        write.assert_called_once()
        self.assertEqual(write.call_args[0][3], 'create_bookmark')
        self.assertEqual(write.call_args[0][4]['tags'], ['AWS', 'Django'])
        review.refresh_from_db()
        self.assertEqual(review.status, 'applied')

    def test_new_tag_for_existing_bookmark_uses_mcp_and_clearing_tags_works(self):
        review = self.review()
        with mock.patch('dwiest.django.demos.bookmarks.ai_service.execute_call', side_effect=self.fake_write) as write:
            result = self.client.post(self.review_url(review), self.posted(tags='AWS\nDjango'))
        self.assertEqual(result.status_code, 302)
        self.assertEqual([c[0][3] for c in write.call_args_list], ['create_tag', 'update_bookmark'])
        self.bookmark.refresh_from_db()
        review = self.review()
        with mock.patch('dwiest.django.demos.bookmarks.ai_service.execute_call', side_effect=self.fake_write):
            self.client.post(self.review_url(review), self.posted(tags=''))
        self.assertFalse(BookmarkTag.objects.filter(bookmark=self.bookmark).exists())

    def test_cancellation_expiry_stale_data_and_duplicates_never_write(self):
        for state in ['cancel', 'expired', 'stale', 'duplicate']:
            review = self.review()
            if state == 'expired':
                review.expires_at = timezone.now() - timedelta(seconds=1)
                review.save()
            if state == 'stale':
                self.bookmark.title = 'Changed elsewhere'
                self.bookmark.save()
            with mock.patch('dwiest.django.demos.bookmarks.ai_service.execute_call') as write:
                if state == 'duplicate':
                    review.status = 'applying'
                    review.save()
                self.client.post(self.review_url(review), self.posted(action='cancel' if state == 'cancel' else 'apply'))
                write.assert_not_called()

    def test_partial_failure_does_not_replay_writes(self):
        review = self.review()
        def partial(*args, **kwargs):
            if args[3] == 'create_tag':
                return self.fake_write(*args, **kwargs)
            raise AIError('Connection timed out.')
        with mock.patch('dwiest.django.demos.bookmarks.ai_service.execute_call', side_effect=partial) as write:
            result = self.client.post(self.review_url(review), self.posted(tags='NewTag'))
            count = write.call_count
            again = self.client.post(self.review_url(review), self.posted(tags='NewTag'))
        self.assertEqual(write.call_count, count)
        review.refresh_from_db()
        self.assertEqual(review.status, 'uncertain')
        self.assertTrue(Tag.objects.filter(owner=self.user, title='NewTag').exists())
        self.assertContains(result, 'Some operations may have completed')
        self.assertContains(again, 'already been handled')

    def test_native_mcp_approval_validates_exact_arguments(self):
        args = {'bookmark_id': self.bookmark.pk, 'changes': {'title': 'Approved'}}
        pending = {'type': 'mcp_approval_request', 'id': 'approval_1', 'server_label': 'bookmarks', 'name': 'update_bookmark', 'arguments': json.dumps(args)}
        with mock.patch('dwiest.django.demos.bookmarks.ai_service.openai_request', side_effect=[response(pending), response(call('update_bookmark', {'id': self.bookmark.pk}))]) as api:
            execute_call(self.user, API_KEY, self.prefs, 'update_bookmark', args)
        approved = api.call_args_list[1][0][1]
        self.assertEqual(approved['input'], [{'type': 'mcp_approval_response', 'approval_request_id': 'approval_1', 'approve': True}])
        self.assertEqual(approved['tool_choice'], 'none')
        pending['arguments'] = json.dumps(dict(args, changes={'title': 'Changed by model'}))
        with mock.patch('dwiest.django.demos.bookmarks.ai_service.openai_request', return_value=response(pending)) as api:
            with self.assertRaisesRegex(AIError, 'differed from your approved values'):
                execute_call(self.user, API_KEY, self.prefs, 'update_bookmark', args)
            self.assertEqual(api.call_count, 1)

    def test_multiple_or_followup_calls_never_approved(self):
        pending = {'type': 'mcp_approval_request', 'id': 'approval', 'name': 'delete_bookmark', 'server_label': 'bookmarks', 'arguments': '{}'}
        for result in [response(pending), response(pending, dict(pending, id='second'))]:
            with mock.patch('dwiest.django.demos.bookmarks.ai_service.openai_request', return_value=result) as api:
                with self.assertRaises(AIError):
                    execute_call(self.user, API_KEY, self.prefs, 'create_tag', {'title': 'A'})
                self.assertEqual(api.call_count, 1)

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

    def test_stale_check_runs_after_preparation_before_native_approval(self):
        args = {'bookmark_id': self.bookmark.pk, 'changes': {'title': 'Approved'}}
        pending = {'type': 'mcp_approval_request', 'id': 'approval', 'server_label': 'bookmarks',
                   'name': 'update_bookmark', 'arguments': json.dumps(args)}
        with mock.patch('dwiest.django.demos.bookmarks.ai_service.openai_request', return_value=response(pending)) as api:
            with self.assertRaisesRegex(AIError, 'stale'):
                execute_call(self.user, API_KEY, self.prefs, 'update_bookmark', args,
                             before_approve=mock.Mock(side_effect=AIError('stale')))
        self.assertEqual(api.call_count, 1)

    def test_full_review_to_native_approval_to_mcp_result(self):
        review = self.review()
        calls = []
        def provider(key, payload):
            self.assertEqual(key, API_KEY)
            calls.append(payload)
            if 'previous_response_id' not in payload:
                spec = json.loads(payload['input'])
                return response({'type': 'mcp_approval_request', 'id': 'approval', 'server_label': 'bookmarks',
                                 'name': spec['tool'], 'arguments': json.dumps(spec['arguments'])})
            spec = json.loads(calls[0]['input'])
            result = self.fake_write(self.user, key, self.prefs, spec['tool'], spec['arguments'])
            return response(call(spec['tool'], {'content': [{'type': 'text', 'text': json.dumps(result)}]}))
        with mock.patch('dwiest.django.demos.bookmarks.ai_service.openai_request', side_effect=provider):
            result = self.client.post(self.review_url(review), self.posted(selected=['title'], title='Reviewed title'))
        self.assertEqual(result.status_code, 302)
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0]['tools'][0]['allowed_tools'], ['update_bookmark'])
        self.assertTrue(calls[1]['input'][0]['approve'])
        self.bookmark.refresh_from_db()
        self.assertEqual(self.bookmark.title, 'Reviewed title')
