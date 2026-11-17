"""Real migrations and auth for application-grant integration tests."""
from .test_bookmarks_ai_settings import *

INSTALLED_APPS = INSTALLED_APPS + ['django.contrib.admin']
MIGRATION_MODULES = {}
ROOT_URLCONF = 'dwiest.django.demos.test_application_urls'
APPLICATION_ACCESS_ENABLED = True
DESKTOP_TOYS_BASE_URL = 'https://toys.example.test/desktop-toys/'
LOGIN_URL = '/login/'
MIDDLEWARE = [
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'dwiest.django.demos.application_access.ApplicationAccessMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
]
