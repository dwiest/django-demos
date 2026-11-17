"""Exercise historical Inventory adoption in an isolated database, not by rolling back the test suite."""
import os
from pathlib import Path
import subprocess
import sys
from django.test import SimpleTestCase


class UmbrellaMigrationTests(SimpleTestCase):
    def test_adopts_legacy_tables_and_enables_ledger_writes(self):
        script = r"""
import django
from django.conf import settings
settings.configure(SECRET_KEY='inventory-adoption-test', INSTALLED_APPS=['django.contrib.auth','django.contrib.contenttypes','django.contrib.sessions','rest_framework','dwiest.django.demos'], DATABASES={'default':{'ENGINE':'django.db.backends.sqlite3','NAME':':memory:'}}, DEFAULT_AUTO_FIELD='django.db.models.BigAutoField', ROOT_URLCONF='dwiest.django.demos.inventory.api_urls', USE_TZ=True, MIDDLEWARE=[], PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
django.setup()
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.loader import MigrationLoader

def migrate(name):
    x = MigrationExecutor(connection)
    x.loader = MigrationLoader(connection, replace_migrations=False)
    x.migrate([('demos', name)])

migrate('0006_bookmark')
from django.contrib.auth.models import User
from dwiest.django.demos.inventory.models import InventoryEntry, InventoryItem, InventoryList, InventoryTransaction
from rest_framework.test import APIClient
# Recreate the pre-existing umbrella layout without migrating a second branch.
with connection.schema_editor() as editor:
    for model in (InventoryItem, InventoryList, InventoryEntry):
        editor.create_model(model)
assert 'demos_inventorytransaction' not in connection.introspection.table_names()
user = User.objects.create_user('legacy-owner')
item = InventoryItem.objects.create(owner=user, name='Legacy apples', description='Fruit')
location = InventoryList.objects.create(owner=user, name='Legacy fridge', description='Cold')
entry = InventoryEntry.objects.create(owner=user, item=item, inventory_list=location, quantity=7)
original = (entry.pk,item.pk,location.pk)
migrate('0008_inventorytransaction')
entry.refresh_from_db()
assert (entry.pk,entry.item_id,entry.inventory_list_id) == original
assert entry.quantity == 7 and InventoryTransaction.objects.count() == 0
client = APIClient();client.force_authenticate(user)
response = client.post('/entries/', {'item':item.pk,'inventory_list':location.pk,'quantity':1}, format='json')
assert response.status_code == 201, response.data
assert client.get('/transactions/').data['count'] == 1
response = client.post('/entries/%s/adjust/' % entry.pk, {'operation':'add','quantity':2,'idempotency_key':'legacy-test'}, format='json')
assert response.status_code == 200, response.data
assert response.data['before'] == 7 and response.data['after'] == 9
"""
        result = subprocess.run([sys.executable, '-c', script], cwd=str(Path(__file__).parents[4]), capture_output=True, text=True, env=os.environ.copy())
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
