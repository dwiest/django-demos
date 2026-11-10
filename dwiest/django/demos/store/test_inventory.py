from django.test import TestCase, Client, override_settings
from django.db import transaction
from .inventory import InventoryError, movement
from .models import ProductVariant, StockMovement, StoreOrder, ShippingAddress
from .test_orders import OrderTests


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class InventoryTests(OrderTests):
    # Reuse checkout and order edit helpers while running the commerce regression
    # cases against stocked merchandise as well as the existing POD defaults.
    def setUp(self):
        super().setUp()
        ProductVariant.objects.filter(pk=self.variant.pk).update(fulfillment_method='stock')
        movement(self.variant.pk, on_hand=10, reason='Opening count', actor=self.manager)
        self.variant.refresh_from_db()

    def balances(self, on_hand, reserved):
        self.variant.refresh_from_db()
        self.assertEqual((self.variant.stock_on_hand, self.variant.stock_reserved), (on_hand, reserved))

    def test_hybrid_splits_and_snapshots_estimates(self):
        ProductVariant.objects.filter(pk=self.variant.pk).update(fulfillment_method='hybrid',
            stock_estimate='Ships tomorrow', production_estimate='Made in 7 days')
        movement(self.variant.pk, on_hand=-9, reason='Correction')
        order = self.place()
        item = order.items.get()
        self.assertEqual((item.stock_quantity, item.pod_quantity), (1, 1))
        self.assertIn('Ships tomorrow', item.delivery_estimate)
        self.assertIn('Made in 7 days', item.delivery_estimate)
        self.balances(1, 1)

    def test_reserve_cancel_and_message_are_idempotent(self):
        order = self.place()
        self.balances(10, 2)
        self.client.post(self.url('checkout'), self.data)
        self.balances(10, 2)
        self.client.force_login(self.manager)
        self.client.post(self.url('order_edit', order.pk), self.edit_data(order, status='cancelled'))
        self.balances(10, 0)
        order.refresh_from_db()
        self.client.post(self.url('order_edit', order.pk), self.edit_data(order, message='Update'))
        self.balances(10, 0)

    def test_shipping_consumes_stock_only_once(self):
        order = self.place()
        self.client.force_login(self.manager)
        self.client.post(self.url('order_edit', order.pk), self.edit_data(order, status='fulfilled', tracking_number='9400'))
        self.balances(8, 0)
        order.refresh_from_db()
        self.client.post(self.url('order_edit', order.pk), self.edit_data(order, tracking_number='9400', message='Thanks'))
        self.balances(8, 0)

    def test_order_quantity_revisions_and_atomic_failure(self):
        order = self.place()
        self.client.force_login(self.manager)
        self.client.post(self.url('order_edit', order.pk), self.edit_data(order, **{'form-0-quantity': 4}))
        self.balances(10, 4)
        response = self.client.post(self.url('order_edit', order.pk), self.edit_data(order, **{'form-0-quantity': 11, 'address-line1': 'Must not save'}))
        self.assertContains(response, 'only 10 available')
        self.balances(10, 4)
        self.assertEqual(order.items.get().quantity, 4)
        order.shipping_address.refresh_from_db()
        self.assertEqual(order.shipping_address.line1, '123 Main St')
        self.client.post(self.url('order_edit', order.pk), self.edit_data(order, **{'form-0-quantity': 1}))
        self.balances(10, 1)

    def test_coming_soon_is_visible_and_rejects_direct_post_and_stale_cart(self):
        ProductVariant.objects.filter(pk=self.variant.pk).update(coming_soon=True)
        self.assertContains(self.client.get(self.url('home')), 'Coming soon')
        self.assertContains(self.client.get(self.url('product', 'pin')), 'Coming soon')
        response = self.client.post(self.url('add', 'pin'), {'variant': self.variant.pk, 'quantity': 1})
        self.assertContains(response, 'Coming soon')
        self.client.post(self.url('checkout'), self.data)
        response = self.client.post(self.url('checkout'), dict(self.data, action='submit'))
        self.assertContains(response, 'Coming soon')
        self.assertFalse(StoreOrder.objects.exists())
        self.assertFalse(ShippingAddress.objects.exists())
        self.balances(10, 0)

    def test_stock_disappears_after_review(self):
        self.client.post(self.url('checkout'), self.data)
        movement(self.variant.pk, on_hand=-10, reason='Damaged')
        response = self.client.post(self.url('checkout'), dict(self.data, action='submit'))
        self.assertContains(response, 'Your order changed')
        self.assertFalse(StoreOrder.objects.exists())

    def test_conditional_updates_reject_second_reservation_and_negative_adjustments(self):
        movement(self.variant.pk, reserved=10, reason='Other orders')
        for kwargs in [dict(reserved=1), dict(on_hand=-1), dict(reserved=-11)]:
            with self.assertRaises(InventoryError):
                movement(self.variant.pk, reason='Must fail', **kwargs)
        self.balances(10, 10)
        self.assertEqual(StockMovement.objects.count(), 2)

    def test_inventory_management_permissions_and_audit(self):
        self.assertEqual(Client().get(self.url('inventory')).status_code, 403)
        self.client.force_login(self.manager)
        response = self.client.post(self.url('inventory'), {'variant': self.variant.pk, 'quantity': 3, 'reason': 'Supplier delivery'})
        self.assertRedirects(response, self.url('inventory'))
        self.balances(13, 0)
        entry = StockMovement.objects.first()
        self.assertEqual(entry.actor, self.manager)
        self.assertEqual(entry.reason, 'Supplier delivery')
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.manager)
        self.assertEqual(strict.post(self.url('inventory'), {}).status_code, 403)

    def test_historical_order_cancellation_does_not_create_inventory(self):
        order = self.place()
        item = order.items.get()
        item.inventory_tracked = False
        item.stock_quantity = 0
        item.save()
        movement(self.variant.pk, reserved=-2, reason='Historical fixture')
        self.client.force_login(self.manager)
        self.client.post(self.url('order_edit', order.pk), self.edit_data(order, status='cancelled'))
        self.balances(10, 0)

    def test_product_edit_preserves_newer_stock_counters(self):
        from .forms import VariantForm
        stale = ProductVariant.objects.get(pk=self.variant.pk)
        movement(self.variant.pk, reserved=2, reason='Concurrent checkout')
        form = VariantForm({'name': stale.name, 'sku': stale.sku, 'price': '21.00',
                            'active': 'on', 'fulfillment_method': 'stock'}, instance=stale)
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.balances(10, 2)

    def test_product_editor_prevents_deleting_stock_history(self):
        self.client.force_login(self.manager)
        product = self.variant.product
        response = self.client.post(self.url('product_edit', product.pk), {
            'name': product.name, 'slug': product.slug, 'published': 'on',
            'variants-TOTAL_FORMS': '1', 'variants-INITIAL_FORMS': '1',
            'variants-MIN_NUM_FORMS': '1', 'variants-MAX_NUM_FORMS': '1000',
            'variants-0-id': self.variant.pk, 'variants-0-name': self.variant.name,
            'variants-0-sku': self.variant.sku, 'variants-0-price': '20.00',
            'variants-0-fulfillment_method': 'stock', 'variants-0-DELETE': 'on',
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(ProductVariant.objects.filter(pk=self.variant.pk).exists())

    def test_stock_only_cart_rejects_excess_and_sold_out_remains_visible(self):
        response = self.client.post(self.url('add', 'pin'), {'variant': self.variant.pk, 'quantity': 9})
        self.assertContains(response, 'only 10 available')
        movement(self.variant.pk, on_hand=-10, reason='Sold elsewhere')
        response = self.client.get(self.url('home'))
        self.assertContains(response, 'Sold out')
        self.assertContains(response, 'disabled')
        response = self.client.post(self.url('update', self.variant.pk), {'quantity': 1})
        self.assertContains(response, 'Sold out')
