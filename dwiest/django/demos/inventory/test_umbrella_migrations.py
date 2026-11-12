"""Regression for the deployed demos_* table layout and legacy data adoption."""
from unittest import skipUnless
from django.apps import apps
from django.contrib.auth.models import User
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from rest_framework.test import APIClient
from .models import InventoryEntry, InventoryItem, InventoryList, InventoryTransaction


@skipUnless(apps.is_installed('dwiest.django.demos'), 'Umbrella-app deployment only')
class UmbrellaMigrationTests(TransactionTestCase):
    def test_adopts_legacy_tables_and_enables_ledger_writes(self):
        target = [('demos', '0008_inventorytransaction')]
        MigrationExecutor(connection).migrate([('demos', '0006_bookmark')])
        try:
            self.assertNotIn('demos_inventorytransaction', connection.introspection.table_names())
            user = User.objects.create_user('legacy-owner')
            item = InventoryItem.objects.create(owner=user, name='Legacy apples', description='Fruit')
            location = InventoryList.objects.create(owner=user, name='Legacy fridge', description='Cold')
            entry = InventoryEntry.objects.create(owner=user, item=item, inventory_list=location, quantity=7)
            original = (entry.pk, item.pk, location.pk)
            MigrationExecutor(connection).migrate(target)
            entry.refresh_from_db()
            self.assertEqual((entry.pk, entry.item_id, entry.inventory_list_id), original)
            self.assertEqual(entry.quantity, 7)
            self.assertEqual(InventoryTransaction.objects.count(), 0)
            client = APIClient()
            client.force_authenticate(user)
            response = client.post('/entries/', {'item': item.pk, 'inventory_list': location.pk,
                                               'quantity': 1}, format='json')
            self.assertEqual(response.status_code, 201, response.data)
            self.assertEqual(client.get('/transactions/').data['count'], 1)
            response = client.post('/entries/%s/adjust/' % entry.pk,
                {'operation': 'add', 'quantity': 2, 'idempotency_key': 'legacy-test'}, format='json')
            self.assertEqual(response.status_code, 200, response.data)
            self.assertEqual(response.data['before'], 7)
            self.assertEqual(response.data['after'], 9)
        finally:
            MigrationExecutor(connection).migrate(target)
