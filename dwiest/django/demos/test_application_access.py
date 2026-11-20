import base64
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Group, Permission
from django.template import RequestContext, engines
from django.test import Client, RequestFactory, TestCase, override_settings
from django.urls import resolve

from .application_access import ApplicationAccess, application_response, navigation
from .application_catalog import APPLICATIONS, BY_KEY
from .application_models import Application
from .inventory.models import InventoryItem


class ApplicationAccessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.user = User.objects.create_user(username='viewer', password='password')
        cls.other = User.objects.create_user(username='other', password='password')
        cls.admin = User.objects.create_superuser(username='operator', password='password')

    def grant(self, *keys, user=None, group=None):
        permissions = Permission.objects.filter(
            content_type__app_label='demos', content_type__model='application',
            codename__in=[BY_KEY[key].codename for key in keys])
        target = group.permissions if group else (user or self.user).user_permissions
        target.add(*permissions)
        return get_user_model().objects.get(pk=(user or self.user).pk)

    def request(self, user=None, url='/apps/demos/'):
        request = RequestFactory().get(url)
        request.user = user or self.user
        request.resolver_match = resolve(url)
        return request

    def render_menu(self, request, services=True):
        return engines['django'].engine.get_template(
            'dwiest-django-demos/components/apps_navigation.html').render(
                RequestContext(request, {'request': request, 'apps_services': services,
                                         'apps_home_url': '/apps/home/'}))

    def test_migration_seeds_complete_catalog_and_native_permissions(self):
        self.assertEqual(set(Application.objects.values_list('key', flat=True)), set(BY_KEY))
        self.assertEqual(sum(app.category == 'toys' for app in APPLICATIONS), 13)
        for app in APPLICATIONS:
            self.assertTrue(Permission.objects.filter(
                content_type__app_label='demos', content_type__model='application',
                codename=app.codename).exists())

    def test_new_user_gets_home_and_no_application_links(self):
        menu = self.render_menu(self.request())
        self.assertIn('href="/apps/home/"', menu)
        self.assertIn('No applications have been enabled', menu)
        self.assertNotIn('role="tab"', menu)
        self.assertNotIn('>Bookmarks</a>', menu)
        self.assertFalse(ApplicationAccess(self.user).allows('unregistered_app'))

    def test_group_and_individual_grants_combine_and_hide_empty_categories(self):
        group = Group.objects.create(name='Demo users')
        user = self.grant('bookmarks', group=group)
        user.groups.add(group)
        user = self.grant('toy_fireworks')
        catalog = navigation(self.request(user))
        self.assertEqual([group['key'] for group in catalog['groups']], ['applications', 'toys'])
        self.assertEqual(set(catalog['by_key']), {'bookmarks', 'toy_fireworks'})
        menu = self.render_menu(self.request(user))
        self.assertIn('>Bookmarks</a>', menu)
        self.assertIn('>Pixel Fireworks</a>', menu)
        self.assertIn('1 toy</p>', menu)
        self.assertNotIn('>Inventory</a>', menu)
        self.assertNotIn('>Services</button>', menu)

    def test_global_switch_applies_even_to_superusers(self):
        self.assertTrue(ApplicationAccess(self.admin).allows('bookmarks'))
        Application.objects.filter(key='bookmarks').update(enabled=False)
        self.assertFalse(ApplicationAccess(self.admin).allows('bookmarks'))
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get('/apps/demos/bookmarks/').status_code, 403)

    def test_inactive_and_anonymous_users_have_no_grants(self):
        self.user.is_active = False
        self.assertFalse(ApplicationAccess(self.user).allows('bookmarks'))
        self.assertFalse(ApplicationAccess(AnonymousUser()).allows('toy_fireworks'))

    def test_browser_guard_covers_nested_urls_and_unknown_namespaces(self):
        self.client.force_login(self.user)
        denied = self.client.get('/apps/demos/bookmarks/child/')
        self.assertEqual(denied.status_code, 403)
        self.assertContains(denied, 'Application unavailable', status_code=403)
        self.grant('bookmarks')
        self.assertEqual(self.client.get('/apps/demos/bookmarks/child/').status_code, 200)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get('/apps/demos/new-app/').status_code, 403)

    def test_anonymous_browser_redirect_preserves_destination(self):
        response = self.client.get('/apps/demos/journal/child/?page=2')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/?next=', response.url)
        self.assertIn('page%3D2', response.url)

    def test_api_checks_basic_identity_after_authentication(self):
        token = base64.b64encode(b'viewer:password').decode('ascii')
        headers = {'HTTP_AUTHORIZATION': 'Basic ' + token}
        url = '/apps/demos/bookmarks/api/'
        self.assertEqual(self.client.get(url, **headers).status_code, 403)
        self.grant('bookmarks')
        response = self.client.get(url, **headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['user'], 'viewer')
        self.assertEqual(self.client.post(url, data={}, **headers).status_code, 200)
        self.assertEqual(self.client.get(url, HTTP_AUTHORIZATION='Basic broken').status_code, 401)

    def test_api_session_auth_and_existing_ownership_are_preserved(self):
        InventoryItem.objects.create(owner=self.user, name='Mine', description='')
        InventoryItem.objects.create(owner=self.other, name='Other', description='')
        self.client.force_login(self.user)
        url = '/apps/demos/inventory/api/items/'
        self.assertEqual(self.client.get(url).status_code, 403)
        self.grant('inventory')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual([item['name'] for item in response.json()['results']], ['Mine'])

    def test_actual_bookmark_bulk_api_obeys_the_same_grant(self):
        import json
        self.client.force_login(self.user)
        body = json.dumps({'items': [{'client_ref': 'one', 'url': 'https://example.com/'}]})
        url = '/apps/demos/bookmarks/bulk/'
        self.assertEqual(self.client.post(url, body, content_type='application/json').status_code, 403)
        self.grant('bookmarks')
        self.assertEqual(self.client.post(url, body, content_type='application/json').status_code, 200)

    def test_bookmark_api_grant_does_not_expose_other_users_records(self):
        from .bookmarks.models import Bookmark
        self.grant('bookmarks')
        self.client.force_login(self.user)
        Bookmark.objects.create(owner=self.other, url='https://example.com/private', title='Private')
        url = '/apps/demos/bookmarks/lookup/?url=https://example.com/private'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()['exists'])
        with override_settings(BOOKMARKS_API_OWNER_ID=self.other.pk):
            self.assertEqual(self.client.get(url).status_code, 403)
        with override_settings(BOOKMARKS_API_OWNER_ID=self.user.pk):
            self.assertEqual(self.client.get(url).status_code, 200)

    def test_api_marker_alone_does_not_bypass_permission_check(self):
        self.grant('bookmarks')
        callback = SimpleNamespace(cls=SimpleNamespace(application_key='bookmarks', permission_classes=[]))
        response = application_response(self.request(url='/apps/demos/bookmarks/'), callback)
        self.assertEqual(response.status_code, 403)

    def test_public_storefront_and_external_toy_urls_keep_existing_behavior(self):
        self.assertEqual(self.client.get('/apps/demos/store/').status_code, 200)
        self.assertEqual(self.client.get('/desktop-toys/fireworks/index.html').status_code, 200)
        self.assertNotIn('store', navigation(self.request())['by_key'])

    def test_filtered_toy_gallery_and_configurable_base_url(self):
        self.grant('toy_fireworks', 'toy_galaga')
        self.client.force_login(self.user)
        response = self.client.get('/apps/demos/toys/')
        self.assertContains(response, '2 toys available')
        self.assertContains(response, 'https://toys.example.test/desktop-toys/fireworks/index.html')
        self.assertContains(response, 'https://toys.example.test/desktop-toys/galaga/index.html')
        self.assertNotContains(response, 'Spinning Sticks')
        with override_settings(DESKTOP_TOYS_BASE_URL=''):
            self.assertNotIn('toys', [group['key'] for group in navigation(self.request())['groups']])

    def test_services_and_current_application_follow_grants(self):
        user = self.grant('environment_status', 'bookmarks')
        request = self.request(user, '/apps/demos/bookmarks/child/')
        catalog = navigation(request, services=True)
        self.assertTrue(catalog['by_key']['bookmarks']['current'])
        self.assertEqual([group['key'] for group in catalog['groups']], ['applications', 'services'])
        self.client.force_login(self.other)
        self.assertEqual(self.client.get('/apps/status/').status_code, 403)
        self.client.force_login(user)
        self.assertEqual(self.client.get('/apps/status/').status_code, 200)

    def test_legacy_rest_administration_requires_staff_and_explicit_grant(self):
        user = self.grant('restapi')
        self.assertFalse(ApplicationAccess(user).allows('restapi'))
        user.is_staff = True
        self.assertTrue(ApplicationAccess(user).allows('restapi'))

    def test_admin_api_also_requires_model_action_permissions(self):
        user = self.grant('restapi')
        user.is_staff = True
        user.save()
        self.client.force_login(user)
        self.assertEqual(self.client.get('/apps/demos/restapi/users/').status_code, 403)
        user.user_permissions.add(Permission.objects.get(
            content_type__app_label='auth', codename='view_user'))
        self.assertEqual(self.client.get('/apps/demos/restapi/users/').status_code, 200)
        self.assertEqual(self.client.post('/apps/demos/restapi/users/', {}).status_code, 403)

    def test_revoking_a_group_grant_takes_effect_on_the_next_request(self):
        group = Group.objects.create(name='Temporary access')
        user = self.grant('bookmarks', group=group)
        user.groups.add(group)
        self.client.force_login(user)
        self.assertEqual(self.client.get('/apps/demos/bookmarks/').status_code, 200)
        user.groups.remove(group)
        self.assertEqual(self.client.get('/apps/demos/bookmarks/').status_code, 403)

    def test_enabled_rows_are_loaded_once_for_a_complete_menu(self):
        user = self.grant('bookmarks', 'inventory', 'toy_fireworks')
        user.get_all_permissions()
        with self.assertNumQueries(1):
            navigation(self.request(user), services=True)

    def test_session_api_still_requires_csrf_for_writes(self):
        self.grant('bookmarks')
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.assertEqual(client.post('/apps/demos/bookmarks/api/', {}).status_code, 403)

    def test_personalized_pages_are_private_and_vary_by_cookie(self):
        self.client.force_login(self.user)
        response = self.client.get('/apps/demos/')
        self.assertIn('private', response['Cache-Control'])
        self.assertIn('Cookie', response['Vary'])

    def test_denied_websocket_is_closed_before_data_is_loaded(self):
        import asyncio
        from .news.consumers import NewsFeed
        consumer = object.__new__(NewsFeed)
        consumer.scope = {'user': AnonymousUser()}
        closed = []

        async def close(code):
            closed.append(code)

        consumer.close = close
        asyncio.run(consumer.websocket_connect({}))
        self.assertEqual(closed, [4403])
