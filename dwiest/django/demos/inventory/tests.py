from unittest.mock import patch
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db.models.deletion import ProtectedError
from django.test import TestCase, override_settings
from django.urls import resolve, reverse
from rest_framework.test import APIClient
from .models import InventoryItem, InventoryList, InventoryEntry, InventoryTransaction
from .services import create_entry, adjust_quantity
from .forms import InventoryEntryForm


class InventoryTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('owner', password='pass')
        self.other = User.objects.create_user('other')
        self.item = InventoryItem.objects.create(owner=self.user, name='Apples', description='Fruit')
        self.inventory_list = InventoryList.objects.create(owner=self.user, name='Pantry', description='Food')
        self.entry = create_entry(owner=self.user, item_id=self.item.pk,
                                  inventory_list_id=self.inventory_list.pk, quantity=5)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def adjust(self, **kwargs):
        values = dict(owner=self.user, entry_id=self.entry.pk, operation='add', quantity=3)
        values.update(kwargs)
        return adjust_quantity(**values)

    def test_operations_and_history(self):
        self.assertEqual(self.adjust().after, 8)
        self.assertEqual(self.adjust(operation='remove', quantity=2).after, 6)
        event = self.adjust(operation='set', quantity=0)
        self.assertEqual((event.before, event.after), (6, 0))
        self.assertEqual(self.entry.transactions.count(), 4)

    def test_retry_and_conflicting_key(self):
        event = self.adjust(idempotency_key='trip-1')
        self.assertEqual(self.adjust(idempotency_key='trip-1').pk, event.pk)
        with self.assertRaises(ValidationError):
            self.adjust(idempotency_key='trip-1', quantity=2)
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.quantity, 8)

    def test_invalid_quantities(self):
        for quantity in (-1, True, 1.5, '3', 2147483648):
            with self.assertRaises(ValidationError):
                self.adjust(quantity=quantity)
        with self.assertRaises(ValidationError):
            self.adjust(operation='remove', quantity=6)
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.quantity, 5)

    def test_ledger_failure_rolls_back(self):
        with patch.object(InventoryTransaction.objects, 'create', side_effect=RuntimeError):
            with self.assertRaises(RuntimeError):
                self.adjust()
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.quantity, 5)

    def test_history_protects_deletion(self):
        with self.assertRaises(ProtectedError):
            self.entry.delete()

    def test_api_auth_and_ownership(self):
        self.client.force_authenticate(None)
        self.assertIn(self.client.get('/items/').status_code, (401, 403))
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get('/entries/').data['count'], 0)
        self.assertEqual(self.client.get('/entries/%s/' % self.entry.pk).status_code, 404)
        self.assertEqual(self.client.post('/entries/%s/adjust/' % self.entry.pk,
            {'operation': 'add', 'quantity': 1, 'idempotency_key': 'foreign'}, format='json').status_code, 404)
        self.assertEqual(self.client.post('/entries/', {'item': self.item.pk,
            'inventory_list': self.inventory_list.pk, 'quantity': 2}, format='json').status_code, 400)

    def test_api_adjust_and_history(self):
        url = '/entries/%s/adjust/' % self.entry.pk
        payload = {'operation': 'add', 'quantity': 2, 'idempotency_key': 'photo-1',
                   'metadata': {'confidence': 0.8}}
        first = self.client.post(url, payload, format='json')
        self.assertEqual(first.status_code, 200, first.data)
        self.assertEqual(self.client.post(url, payload, format='json').data, first.data)
        self.assertEqual(self.client.get('/entries/%s/transactions/' % self.entry.pk).data['count'], 2)
        self.assertEqual(self.client.patch('/entries/%s/' % self.entry.pk,
            {'quantity': 9}, format='json').status_code, 405)
        self.assertEqual(self.client.post(url, {'operation': 'add', 'quantity': 2}, format='json').status_code, 400)

    def test_api_create_search_update(self):
        response = self.client.post('/items/', {'name': 'Milk', 'description': 'Dairy'}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(self.client.get('/items/?term=milk').data['count'], 1)
        response = self.client.patch('/items/%s/' % response.data['id'], {'description': 'Fresh'}, format='json')
        self.assertEqual(response.status_code, 200)
        response = self.client.post('/entries/', {'item': self.item.pk,
            'inventory_list': self.inventory_list.pk, 'quantity': 2}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(InventoryTransaction.objects.filter(entry_id=response.data['id']).count(), 1)

    def test_manual_form_uses_service(self):
        form = InventoryEntryForm(instance=self.entry, data={'item': self.item.pk,
            'inventory_list': self.inventory_list.pk, 'quantity': 9, 'status': 0})
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.assertEqual(self.entry.transactions.first().after, 9)


@override_settings(ROOT_URLCONF='dwiest.django.demos.inventory.urls')
class InventoryURLTests(TestCase):
    def test_inventory_mount_loads_ui_and_api_routes(self):
        self.assertEqual(reverse('home'), '/')
        self.assertEqual(reverse('api_items'), '/api/items/')
        self.assertEqual(resolve('/api/entries/1/adjust/').url_name, 'api_adjust')
