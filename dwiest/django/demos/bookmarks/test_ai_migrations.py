"""Run the real migration chain in a separate process/database from UI schema tests."""
import os
from pathlib import Path
import subprocess
import sys
from django.test import SimpleTestCase


class AIMigrationTests(SimpleTestCase):
    def test_upgrade_adds_only_ai_tables_and_retains_bookmark_data(self):
        script = '''
import django
from django.conf import settings
settings.configure(SECRET_KEY='migration-test', INSTALLED_APPS=['django.contrib.auth', 'django.contrib.contenttypes', 'dwiest.django.demos'], DATABASES={'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}}, DEFAULT_AUTO_FIELD='django.db.models.BigAutoField')
django.setup()
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
executor = MigrationExecutor(connection)
executor.migrate([('demos', '0008_inventorytransaction')])
state = executor.loader.project_state([('demos', '0008_inventorytransaction')]).apps
Bookmark = state.get_model('demos', 'Bookmark')
bookmark = Bookmark.objects.create(url='https://example.com/legacy', title='Preserved')
before = set(connection.introspection.table_names())
executor = MigrationExecutor(connection)
executor.migrate([('demos', '0009_bookmark_ai')])
after = set(connection.introspection.table_names())
assert after - before == {'demos_bookmarkaisettings', 'demos_bookmarkaianalysis'}
assert Bookmark.objects.get(pk=bookmark.pk).title == 'Preserved'
state = executor.loader.project_state([('demos', '0009_bookmark_ai')]).apps
User = state.get_model('auth', 'User')
owner = User.objects.create(username='existing-owner')
Preferences = state.get_model('demos', 'BookmarkAISettings')
prefs = Preferences.objects.create(owner=owner, encrypted_api_key='existing-ciphertext', instructions='Keep these', model='existing-model')
executor = MigrationExecutor(connection)
executor.migrate([('demos', '0010_bookmark_ai_blocked_domains')])
assert set(connection.introspection.table_names()) == after
executor = MigrationExecutor(connection)
executor.migrate([('demos', '0011_bookmark_ai_attempt')])
assert set(connection.introspection.table_names()) == after | {'demos_bookmarkaiattempt'}
executor = MigrationExecutor(connection)
executor.migrate([('demos', '0012_bookmark_enrichment')])
assert set(connection.introspection.table_names()) == after | {'demos_bookmarkaiattempt', 'demos_bookmarkenrichmentattempt'}
executor = MigrationExecutor(connection)
executor.migrate([('demos', '0013_bookmark_creation_preferences')])
from dwiest.django.demos.bookmark_ai_models import BookmarkAISettings, BookmarkAIAnalysis, BookmarkAIAttempt, BookmarkEnrichmentAttempt
from django.db.migrations.autodetector import MigrationAutodetector
from django.db.migrations.state import ProjectState
executor = MigrationExecutor(connection)
actual = executor.loader.project_state([('demos', '0013_bookmark_creation_preferences')])
expected = ProjectState.from_apps(django.apps.apps)
for model in (BookmarkAISettings, BookmarkAIAnalysis, BookmarkAIAttempt, BookmarkEnrichmentAttempt):
    key = ('demos', model._meta.model_name)
    assert {n: f.deconstruct()[1:] for n, f in actual.models[key].fields.items()} == {n: f.deconstruct()[1:] for n, f in expected.models[key].fields.items()}
upgraded = BookmarkAISettings.objects.get(pk=prefs.pk)
assert upgraded.blocked_domains == []
assert (upgraded.download_on_create, upgraded.enrich_on_create, upgraded.failed_attempt_retention_days) == (False, False, 30)
assert (upgraded.use_job_service, upgraded.include_raw_html, upgraded.job_retention_days) == (False, True, 365)
assert (upgraded.encrypted_api_key, upgraded.instructions, upgraded.model) == ('existing-ciphertext', 'Keep these', 'existing-model')
upgraded.blocked_domains = ['example.com']
upgraded.save(update_fields=['blocked_domains'])
attempt = BookmarkAIAttempt.objects.create(owner_id=owner.pk, url='https://example.com/new')
assert attempt.last_attempted_at is not None
executor = MigrationExecutor(connection)
executor.migrate([('demos', '0010_bookmark_ai_blocked_domains')])
assert set(connection.introspection.table_names()) == after
executor = MigrationExecutor(connection)
executor.migrate([('demos', '0009_bookmark_ai')])
restored = Preferences.objects.get(pk=prefs.pk)
assert (restored.encrypted_api_key, restored.instructions, restored.model) == ('existing-ciphertext', 'Keep these', 'existing-model')
executor = MigrationExecutor(connection)
executor.migrate([('demos', '0008_inventorytransaction')])
assert Bookmark.objects.get(pk=bookmark.pk).title == 'Preserved'
assert set(connection.introspection.table_names()) == before
'''
        result = subprocess.run([sys.executable, '-c', script], cwd=str(Path(__file__).parents[4]),
                                capture_output=True, text=True, env=os.environ.copy())
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
