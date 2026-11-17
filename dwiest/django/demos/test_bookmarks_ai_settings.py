SECRET_KEY = 'bookmarks-tests-only'
INSTALLED_APPS = ['django.contrib.auth', 'django.contrib.contenttypes', 'django.contrib.sessions',
                  'django.contrib.messages', 'django.contrib.staticfiles', 'rest_framework', 'dwiest.django.demos']
DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}}
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
ROOT_URLCONF = 'dwiest.django.demos.bookmarks.test_urls'
USE_TZ = True
TIME_ZONE = 'America/New_York'
MIDDLEWARE = ['django.contrib.sessions.middleware.SessionMiddleware', 'django.middleware.csrf.CsrfViewMiddleware',
              'django.contrib.auth.middleware.AuthenticationMiddleware', 'django.contrib.messages.middleware.MessageMiddleware']
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
TEMPLATES = [{'BACKEND': 'django.template.backends.django.DjangoTemplates', 'APP_DIRS': True,
              'OPTIONS': {'context_processors': ['django.template.context_processors.request',
                          'django.contrib.auth.context_processors.auth', 'django.contrib.messages.context_processors.messages']}}]
STATIC_URL = '/static/'
ALLOWED_HOSTS = ['testserver', 'localhost', '127.0.0.1']
# The legacy Bookmark/Tag tables predate the current migration state. Build the
# current schema for workflow tests; test_ai_migrations verifies the additive migration.
MIGRATION_MODULES = {'demos': None}
BOOKMARKS_AI_MCP_URL = 'https://example.execute-api.us-east-1.amazonaws.com/api/bookmarks-mcp'
BOOKMARKS_AI_MCP_TOKEN = 'unit-test-only-' + 't' * 40
BOOKMARKS_AI_MODEL = 'test-model'
BOOKMARKS_AI_MODELS = ['test-model']


# These suites exercise application behavior; grant enforcement has its own suite.
APPLICATION_ACCESS_ENABLED = False
