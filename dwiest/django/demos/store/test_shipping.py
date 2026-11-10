from decimal import Decimal
from django.core import mail
from .test_orders import OrderTests
from .models import StoreBranding
from .orders import totals


class ShippingTests(OrderTests):
    def test_rate_and_threshold_after_discount(self):
        StoreBranding.objects.create(shipping_rate='9.00', free_shipping_threshold='50.00', coupon_code='SAVE', coupon_percent=10)
        self.assertEqual(totals(Decimal('50'), 'standard', 'SAVE')['shipping_cost'], Decimal('9'))
        self.assertEqual(totals(Decimal('60'), 'standard', 'SAVE')['shipping_cost'], Decimal('0'))

    def test_partial_duplicate_and_overshipment(self):
        order = self.place()
        self.client.force_login(self.manager)
        data = self.shipment_data(order, 1)
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.client.post(self.url('shipment_create', order.pk), data).status_code, 302)
            self.assertEqual(self.client.post(self.url('shipment_create', order.pk), data).status_code, 302)
        self.assertEqual(order.shipments.count(), 1)
        self.assertEqual(order.fulfillment_status, 'Partially shipped')
        self.assertEqual(len(mail.outbox), 2)
        self.assertIn('Wurm pin', mail.outbox[-1].alternatives[0][0])
        self.assertNotIn('Private supplier note', mail.outbox[-1].body)
        self.assertContains(self.client.post(self.url('shipment_create', order.pk), self.shipment_data(order, 2)), 'exceeds remaining')
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(self.url('shipment_create', order.pk), self.shipment_data(order, 1))
        order.refresh_from_db()
        self.assertEqual(order.status, 'fulfilled')
        self.assertEqual(order.fulfillment_status, 'Shipped')

    def test_tracking_correction_and_explicit_resend(self):
        order = self.place()
        self.client.force_login(self.manager)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(self.url('shipment_create', order.pk), self.shipment_data(order))
        shipment = order.shipments.get()
        data = dict(carrier='UPS', tracking_number='new-number', tracking_url='https://example.com/new', supplier='', private_notes='')
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(self.url('shipment_edit', order.pk, shipment.pk), data)
        self.assertEqual(len(mail.outbox), 2)
        data['action'] = 'notify'
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(self.url('shipment_edit', order.pk, shipment.pk), data)
        self.assertEqual(len(mail.outbox), 3)
        self.assertIn('new-number', mail.outbox[-1].body)

    def test_shipping_requires_staff_permissions(self):
        order = self.place()
        self.assertEqual(self.client.post(self.url('shipment_create', order.pk), self.shipment_data(order)).status_code, 403)
