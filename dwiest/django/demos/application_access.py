"""Application grants; data ownership and action permissions remain in the views."""
from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render
from django.utils.deprecation import MiddlewareMixin
from django.utils.cache import patch_cache_control, patch_vary_headers

from .application_catalog import BY_KEY, CATEGORIES, application_for_match


def access_checks_enabled():
    return getattr(settings, 'APPLICATION_ACCESS_ENABLED', True)


class ApplicationAccess:
    def __init__(self, user):
        self.user = user
        self._enabled = None

    def allows(self, key):
        app = BY_KEY.get(key)
        if app is None:
            return False
        if not access_checks_enabled():
            return True
        user = self.user
        if not getattr(user, 'is_authenticated', False) or not getattr(user, 'is_active', False):
            return False
        if app.staff_required and not user.is_staff:
            return False
        if self._enabled is None:
            from .application_models import Application
            self._enabled = set(Application.objects.filter(enabled=True).values_list('key', flat=True))
        return key in self._enabled and user.has_perm(app.permission)


def for_request(request):
    access = getattr(request, '_application_access', None)
    if access is None:
        access = ApplicationAccess(getattr(request, 'user', None))
        if request is not None:
            request._application_access = access
    return access


def navigation(request, services=False):
    access = for_request(request)
    match = getattr(request, 'resolver_match', None)
    current = application_for_match(match)
    entries = {}
    for key, app in BY_KEY.items():
        if not access.allows(key):
            continue
        url = app.destination()
        if not url:
            continue
        entries[key] = dict(key=key, title=app.title, url=url, category=app.category,
                            section=app.section, description=app.description,
                            current=bool(current and current.key == key))
    groups = []
    for key, title in CATEGORIES:
        if key == 'services' and not services:
            continue
        items = [entry for entry in entries.values()
                 if entry['category'] == key and BY_KEY[entry['key']].listed]
        if not items:
            continue
        sections = []
        for section in dict.fromkeys(item['section'] for item in items):
            section_items = [item for item in items if item['section'] == section]
            sections.append(dict(title=section, items=section_items, rows=(len(section_items) + 1) // 2))
        groups.append(dict(key=key, title=title, items=items, sections=sections))
    active = current.category if current else (
        'toys' if getattr(match, 'url_name', '') == 'desktop_toys' else 'applications')
    if active not in [group['key'] for group in groups]:
        active = groups[0]['key'] if groups else ''
    return dict(groups=groups, by_key=entries, active=active,
                applications=[entry for entry in entries.values() if entry['category'] == 'applications'],
                toys=[entry for entry in entries.values() if entry['category'] == 'toys'])


def application_response(request, view_func):
    if not access_checks_enabled():
        return None
    app = application_for_match(getattr(request, 'resolver_match', None))
    # A newly included demo namespace needs an explicit catalog entry.
    namespaces = getattr(getattr(request, 'resolver_match', None), 'namespaces', ())
    unknown = 'demos' in namespaces and len(namespaces) > namespaces.index('demos') + 1 and app is None
    if not unknown and (app is None or not app.enforce):
        return None
    if getattr(view_func, 'cls', None) is not None:
        # DRF must check the authenticated API user, not the pre-auth session user.
        cls = view_func.cls
        from .application_api import ApplicationPermission
        if (app and getattr(cls, 'application_key', None) == app.key
                and ApplicationPermission in getattr(cls, 'permission_classes', ())):
            return None
        return JsonResponse({'detail': 'This application is unavailable.'}, status=403)
    if not getattr(request.user, 'is_authenticated', False):
        from django.contrib.auth.views import redirect_to_login
        return redirect_to_login(request.get_full_path())
    if not unknown and for_request(request).allows(app.key):
        return None
    return render(request, 'dwiest-django-demos/applications/denied.html', status=403)


class ApplicationAccessMiddleware(MiddlewareMixin):
    def process_view(self, request, view_func, view_args, view_kwargs):
        return application_response(request, view_func)

    def process_response(self, request, response):
        return private_application_response(request, response)


def private_application_response(request, response):
    if getattr(getattr(request, 'user', None), 'is_authenticated', False):
        patch_cache_control(response, private=True)
        patch_vary_headers(response, ('Cookie', 'Authorization'))
    return response
