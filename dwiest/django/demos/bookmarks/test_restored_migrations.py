"""Exercise fresh installs and the exact fully-applied deployed graph in isolated databases."""
import os
from pathlib import Path
import subprocess
import sys
from django.test import SimpleTestCase

SETUP = """
from django.conf import settings
settings.configure(SECRET_KEY='history-tests', INSTALLED_APPS=['django.contrib.auth', 'django.contrib.contenttypes', 'dwiest.django.demos'], DATABASES={'default':{'ENGINE':'django.db.backends.sqlite3','NAME':':memory:'}}, DEFAULT_AUTO_FIELD='django.db.models.BigAutoField')
import django
django.setup()
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.recorder import MigrationRecorder
"""


class RestoredMigrationTests(SimpleTestCase):
    def run_script(self, code):
        result = subprocess.run([sys.executable, '-c', SETUP + code], cwd=str(Path(__file__).parents[4]), capture_output=True, text=True, env=os.environ.copy())
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_fresh_install_has_one_leaf_and_expected_preferences(self):
        self.run_script("""
x = MigrationExecutor(connection)
assert not x.loader.detect_conflicts()
assert x.loader.graph.leaf_nodes('demos') == [('demos','0047_merge_creation_history')]
x.migrate([('demos','0047_merge_creation_history')])
from dwiest.django.demos.bookmark_ai_models import BookmarkAISettings
from django.contrib.auth.models import User
owner = User.objects.create(username='fresh')
prefs = BookmarkAISettings.objects.create(owner=owner)
assert (prefs.download_on_create, prefs.enrich_on_create, prefs.failed_attempt_retention_days) == (False,False,30)
assert {'demos_bookmark','demos_inventoryentry','demos_inventorytransaction','demos_journal','demos_invoice'} <= set(connection.introspection.table_names())
# Runtime registration must never propose deleting recovered legacy tables.
from django.db.migrations.autodetector import MigrationAutodetector
from django.db.migrations.state import ProjectState
from django.apps import apps
x = MigrationExecutor(connection)
changes = MigrationAutodetector(x.loader.project_state(), ProjectState.from_apps(apps))._detect_changes()
assert not changes.get('demos'), [(type(op).__name__, repr(op)) for m in changes.get('demos', []) for op in m.operations]
""")

    def test_existing_0045_upgrade_does_not_recreate_or_drop_tables(self):
        self.run_script("""
# Reproduce deployed order: legacy models first, then modern adoption/AI branch.
x = MigrationExecutor(connection)
x.loader = MigrationLoader(connection, replace_migrations=False)
x.migrate([('demos','0041_alter_lineitem_timeworked')])
x = MigrationExecutor(connection); x.loader = MigrationLoader(connection, replace_migrations=False)
x.migrate([('demos','0045_merge_20261116_2248')])
from django.contrib.auth.models import User
from dwiest.django.demos.bookmarks.models import Bookmark, Tag, BookmarkTag
from dwiest.django.demos.bookmark_ai_models import BookmarkAISettings, BookmarkEnrichmentAttempt
from dwiest.django.demos.inventory.models import InventoryItem, InventoryList, InventoryEntry
owner = User.objects.create(username='existing')
bookmark = Bookmark.objects.create(owner=owner, url='https://example.com/kept', title='Keep title', description='Keep body')
tag = Tag.objects.create(owner=owner, title='Keep tag')
BookmarkTag.objects.create(owner=owner, bookmark=bookmark, tag=tag)
# Historical model avoids querying the new preference columns before migration.
old = x.loader.project_state([('demos','0045_merge_20261116_2248')]).apps.get_model('demos','BookmarkAISettings')
old.objects.create(owner_id=owner.pk, encrypted_api_key='kept-ciphertext', instructions='Keep instructions')
item = InventoryItem.objects.create(owner=owner, name='Keep item', description='Item')
location = InventoryList.objects.create(owner=owner, name='Keep list', description='List')
entry = InventoryEntry.objects.create(owner=owner, item=item, inventory_list=location, quantity=7)
attempt = BookmarkEnrichmentAttempt.objects.create(owner=owner, bookmark_id=bookmark.pk, fingerprint='keep', url=bookmark.url, service_url='https://example.com/service', status='failed')
before = set(connection.introspection.table_names())
# The historical executor's replacement bookkeeping is newer than the deployed fixture.
MigrationRecorder(connection).record_unapplied('demos','0046_squashed_legacy_history')
assert ('demos','0046_squashed_legacy_history') not in MigrationRecorder(connection).applied_migrations()
x = MigrationExecutor(connection)
x.loader.check_consistent_history(connection)
plan = x.migration_plan([('demos','0047_merge_creation_history')])
assert [m.name for m, backwards in plan] == ['0013_bookmark_creation_preferences','0047_merge_creation_history']
from django.test.utils import CaptureQueriesContext
with CaptureQueriesContext(connection) as queries:
    x.migrate([('demos','0047_merge_creation_history')])
# SQLite may rebuild only the preference table while adding fields with defaults.
for query in queries.captured_queries:
    sql = query['sql'].lstrip().upper()
    if sql.startswith(('CREATE TABLE','DROP TABLE','DELETE FROM')):
        assert 'BOOKMARKAISETTINGS' in sql, sql
assert set(connection.introspection.table_names()) == before
bookmark.refresh_from_db(); entry.refresh_from_db(); attempt.refresh_from_db()
assert bookmark.title == 'Keep title' and bookmark.description == 'Keep body'
assert BookmarkTag.objects.filter(bookmark=bookmark, tag=tag).exists()
assert entry.quantity == 7 and attempt.fingerprint == 'keep'
prefs = BookmarkAISettings.objects.get(owner=owner)
assert (prefs.encrypted_api_key, prefs.instructions) == ('kept-ciphertext','Keep instructions')
assert (prefs.download_on_create, prefs.enrich_on_create, prefs.failed_attempt_retention_days) == (False,False,30)
x = MigrationExecutor(connection)
assert x.migration_plan([('demos','0047_merge_creation_history')]) == []
assert not x.loader.detect_conflicts()
# Reversing only PR4 preferences must preserve all old rows and original graph.
x.migrate([('demos','0046_squashed_legacy_history')])
assert old.objects.get(owner_id=owner.pk).encrypted_api_key == 'kept-ciphertext'
assert Bookmark.objects.get(pk=bookmark.pk).title == 'Keep title'
""")
