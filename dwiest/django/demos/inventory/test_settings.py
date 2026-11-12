SECRET_KEY = 'inventory-tests'
INSTALLED_APPS = ['django.contrib.auth', 'django.contrib.contenttypes', 'django.contrib.sessions', 'rest_framework', 'dwiest.django.demos.inventory']
DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}}
DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'
ROOT_URLCONF = 'dwiest.django.demos.inventory.api_urls'
USE_TZ = True
MIDDLEWARE = []
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
