"""Isolated store test configuration; never use in production."""
from pathlib import Path

SECRET_KEY = 'store-tests-only'
INSTALLED_APPS = [
    'django.contrib.auth', 'django.contrib.contenttypes', 'django.contrib.sessions',
    'django.contrib.staticfiles', 'dwiest.django.demos',
    'dwiest.django.demos.store.apps.StoreConfig',
]
DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}}
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
ROOT_URLCONF = 'dwiest.django.demos.store.test_urls'
MIDDLEWARE = [
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
]
TEMPLATES = [{'BACKEND': 'django.template.backends.django.DjangoTemplates', 'APP_DIRS': True,
              'OPTIONS': {'context_processors': [
                  'django.template.context_processors.request',
                  'django.contrib.auth.context_processors.auth',
              ]}}]
STATIC_URL = '/static/'
USE_TZ = True
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
