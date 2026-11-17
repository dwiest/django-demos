"""Render the actual menu for DOM tests; no server or cloud services required."""
import os
from pathlib import Path
import sys

os.environ['DJANGO_SETTINGS_MODULE'] = 'dwiest.django.demos.test_application_settings'
import django
django.setup()

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.template import RequestContext, engines
from django.test import RequestFactory
from django.urls import resolve

call_command('migrate', verbosity=0)
user = get_user_model().objects.create_superuser(username='menu-fixture')
request = RequestFactory().get('/django/demos/')
request.user = user
request.resolver_match = resolve(request.path)
menu = engines['django'].engine.get_template(
    'dwiest-django-demos/components/apps_navigation.html').render(
        RequestContext(request, {'request': request, 'apps_services': True,
                                 'apps_home_url': '/django/home/'}))
Path(sys.argv[1]).write_text('<!doctype html><body>' + menu +
    '<details data-nav-menu id="account"><summary>Account</summary><a href="/logout/">Sign out</a></details>'
    '<details id="filters" open><summary>Filters</summary><input></details>'
    '<button id="outside">Outside</button></body>')
