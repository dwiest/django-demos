from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core import mail
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from .models import Product, ProductVariant, StoreBranding, StoreOrder
from .orders import notify


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class OrderTests(TestCase):
    def setUp(self):
        product = Product.objects.create(name='Wurm pin', slug='pin', published=True)
        self.variant = ProductVariant.objects.create(product=product, sku='WURM', price='20.00')
        self.manager = get_user_model().objects.create_user(username='manager')
        self.manager.user_permissions.set(Permission.objects.filter(content_type__app_label='demo_store'))
        self.client.post(self.url('add', 'pin'), {'variant': self.variant.pk, 'quantity': 2})
        self.client.get(self.url('checkout'))
        self.data = dict(email='buyer@example.com', name='Buyer', line1='123 Main St', line2='',
                         city='Raleigh', state='NC', postal_code='27601', shipping_method='ground',
                         payment_method='card_usd', coupon='discount', acknowledge='on',
                         checkout_key=self.client.session['store_checkout_key'], action='review')

    def url(self, name, *args):
        return reverse('demos:store:' + name, args=args)

    def place(self):
        response = self.client.post(self.url('checkout'), self.data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['form'].errors)
        self.data['action'] = 'submit'
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(self.url('checkout'), self.data)
        self.assertEqual(response.status_code, 302)
        return StoreOrder.objects.get()

    def edit_data(self, order, **changes):
        item = order.items.get()
        data = {'status': order.status, 'tracking_number': '', 'message': '',
                'form-TOTAL_FORMS': '1', 'form-INITIAL_FORMS': '1',
                'form-MIN_NUM_FORMS': '0', 'form-MAX_NUM_FORMS': '1000',
                'form-0-id': item.pk, 'form-0-quantity': item.quantity}
        for field in ['name', 'line1', 'line2', 'city', 'state', 'postal_code']:
            data['address-' + field] = getattr(order.shipping_address, field)
        data.update(changes)
        return data

    def test_checkout_snapshots_totals_email_and_private_receipt(self):
        order = self.place()
        self.assertEqual(order.total, Decimal('44.95'))
        self.assertEqual(order.discount, Decimal('2.00'))
        self.assertTrue(order.payment_acknowledgment.startswith('SIMULATED-'))
        self.assertContains(self.client.get(self.url('order_complete', order.token)), 'Wurm thanks you')
        self.assertEqual(Client().get(self.url('order_complete', order.token)).status_code, 404)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Wurm pin', mail.outbox[0].body)
        self.variant.price = 90
        self.variant.save()
        self.assertEqual(order.items.get().unit_price, Decimal('20.00'))

    def test_duplicate_submission_and_second_order(self):
        first = self.place()
        self.client.post(self.url('checkout'), self.data)
        self.assertEqual(StoreOrder.objects.count(), 1)
        self.client.post(self.url('add', 'pin'), {'variant': self.variant.pk, 'quantity': 1})
        self.client.get(self.url('checkout'))
        self.assertNotEqual(self.client.session['store_checkout_key'], str(first.checkout_key))
        self.assertEqual(self.client.get(self.url('order_complete', first.token)).status_code, 200)

    def test_invalid_coupon_and_address(self):
        for change in [{'coupon': 'NOPE'}, {'state': 'ZZ'}, {'postal_code': 'abc'}, {'shipping_method': 'free'}, {'payment_method': 'paid'}, {'acknowledge': ''}]:
            response = self.client.post(self.url('checkout'), dict(self.data, **change))
            self.assertTrue(response.context['form'].errors)
        self.assertFalse(StoreOrder.objects.exists())

    def test_configurable_coupon_and_usdc(self):
        StoreBranding.objects.create(coupon_code='WURM', coupon_percent=10)
        self.data.update(coupon='wurm', payment_method='usdc')
        order = self.place()
        self.assertEqual(order.total, Decimal('42.95'))
        self.assertEqual(order.payment_method, 'usdc')

    def test_submit_requires_current_review(self):
        self.client.post(self.url('checkout'), self.data)
        self.variant.price = 30
        self.variant.save()
        response = self.client.post(self.url('checkout'), dict(self.data, action='submit'))
        self.assertContains(response, 'Your order changed')
        self.assertFalse(StoreOrder.objects.exists())

    def test_fulfillment_tracking_and_notifications(self):
        order = self.place()
        self.client.force_login(self.manager)
        response = self.client.post(self.url('order_edit', order.pk), self.edit_data(order, status='fulfilled'))
        self.assertContains(response, 'Enter a USPS tracking number')
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(self.url('order_edit', order.pk), self.edit_data(order, status='fulfilled', tracking_number='94000000000000000000'))
        order.refresh_from_db()
        self.assertEqual(order.status, 'fulfilled')
        self.assertIsNotNone(order.fulfilled_at)
        self.assertEqual(len(mail.outbox), 2)
        self.assertContains(self.client.get(self.url('order_edit', order.pk)), 'Order history')

    def test_modify_items_and_address_audited(self):
        order = self.place()
        self.client.force_login(self.manager)
        data = self.edit_data(order, **{'form-0-quantity': 3, 'address-line1': '456 New St'})
        self.assertEqual(self.client.post(self.url('order_edit', order.pk), data).status_code, 302)
        order.refresh_from_db()
        self.assertEqual(order.total, Decimal('63.95'))
        self.assertEqual(order.shipping_address.line1, '456 New St')
        self.assertIn('Items changed', order.events.last().message)

    def test_cancel_and_prevent_later_edits(self):
        order = self.place()
        self.client.force_login(self.manager)
        self.client.post(self.url('order_edit', order.pk), self.edit_data(order, status='cancelled'))
        order.refresh_from_db()
        self.assertIsNotNone(order.cancelled_at)
        response = self.client.post(self.url('order_edit', order.pk), self.edit_data(order, status='placed'))
        self.assertContains(response, 'read-only')
        self.client.post(self.url('order_edit', order.pk), self.edit_data(order, message='A personal update'))
        self.assertEqual(order.events.last().message, 'A personal update')

    def test_notification_failure_retry_does_not_duplicate(self):
        with patch('dwiest.django.demos.store.orders.send_mail', side_effect=RuntimeError('offline')):
            with self.assertLogs('dwiest.django.demos.store.orders', level='ERROR'):
                order = self.place()
        event = order.events.get()
        self.assertTrue(event.email_error)
        notify(event.pk)
        notify(event.pk)
        self.assertEqual(len(mail.outbox), 1)

    def test_management_permissions_and_csrf(self):
        order = self.place()
        self.assertEqual(Client().get(self.url('order_list')).status_code, 403)
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.manager)
        self.assertEqual(strict.post(self.url('order_edit', order.pk), self.edit_data(order)).status_code, 403)
        self.client.force_login(self.manager)
        self.assertContains(self.client.get(self.url('order_list')), order.number)

    def test_coupon_settings_bounds_and_disabling(self):
        from .forms import StoreBrandingForm
        branding = StoreBranding(name='RottenWorld')
        for value in ['-1', '100.01']:
            form = StoreBrandingForm({'name': 'RottenWorld', 'tagline': 'Wurm', 'footer_heading': 'Thanks', 'coupon_percent': value}, instance=branding)
            self.assertIn('coupon_percent', form.errors)
        StoreBranding.objects.create(coupon_code='')
        response = self.client.post(self.url('checkout'), self.data)
        self.assertContains(response, 'That coupon is not active')
        self.data['coupon'] = ''
        self.assertEqual(self.place().discount, 0)

    def test_correct_order_email_audited_and_notifies_new_recipient(self):
        order = self.place()
        self.client.force_login(self.manager)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(self.url('order_email', order.pk), {'email': 'corrected@example.com'})
        self.assertRedirects(response, self.url('order_edit', order.pk))
        order.refresh_from_db()
        self.assertEqual(order.email, 'corrected@example.com')
        event = order.events.last()
        self.assertEqual(event.actor, self.manager)
        self.assertIn('buyer@example.com to corrected@example.com', event.message)
        self.assertEqual(mail.outbox[-1].to, ['corrected@example.com'])
        self.assertEqual(order.status, 'placed')

    def test_email_validation_permissions_and_csrf(self):
        order = self.place()
        self.assertEqual(Client().post(self.url('order_email', order.pk), {'email': 'other@example.com'}).status_code, 403)
        self.client.force_login(self.manager)
        self.assertEqual(self.client.get(self.url('order_email', order.pk)).status_code, 405)
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.manager)
        self.assertEqual(strict.post(self.url('order_email', order.pk), {'email': 'other@example.com'}).status_code, 403)
        response = self.client.post(self.url('order_email', order.pk), {'email': 'invalid'})
        self.assertContains(response, 'Enter a valid email address')
        order.refresh_from_db()
        self.assertEqual(order.email, 'buyer@example.com')
        self.assertEqual(order.events.count(), 1)

    def test_completed_order_email_can_be_corrected_and_failed_email_retried(self):
        order = self.place()
        order.status = 'fulfilled'
        order.save()
        event = order.events.get()
        event.email_sent_at = None
        event.email_error = 'Failed delivery'
        event.save()
        self.client.force_login(self.manager)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(self.url('order_email', order.pk), {'email': 'fixed@example.com'})
        self.client.post(self.url('retry_notification', order.pk, event.pk))
        order.refresh_from_db()
        self.assertEqual(order.status, 'fulfilled')
        self.assertEqual(mail.outbox[-1].to, ['fixed@example.com'])
        event.refresh_from_db()
        self.assertIsNotNone(event.email_sent_at)

    def test_email_branding_plaintext_and_safe_html(self):
        StoreBranding.objects.create(name='RottenWorld', email_header='Hello <Wurm>\nThanks for shopping',
                                     email_footer='Contact us\n<script>bad()</script>')
        self.place()
        message = mail.outbox[-1]
        self.assertTrue(message.subject.startswith('RottenWorld order RW-'))
        self.assertIn('Hello <Wurm>\nThanks for shopping', message.body)
        self.assertIn('Contact us\n<script>bad()</script>', message.body)
        html, mimetype = message.alternatives[0]
        self.assertEqual(mimetype, 'text/html')
        self.assertIn('Hello &lt;Wurm&gt;<br>', html)
        self.assertIn('&lt;script&gt;bad()&lt;/script&gt;', html)
        self.assertNotIn('<script>', html)
        self.assertIn('Wurm pin', html)
        self.assertIn('$44.95 USD', html)

    def test_photo_variant_mapping_rejects_other_products(self):
        from .forms import PhotoDetailsForm
        from .models import ProductPhoto
        photo = ProductPhoto.objects.create(product=self.variant.product, bucket='test', key='mapped-photo',
                                            width=100, height=100)
        other = Product.objects.create(name='Other', slug='other')
        foreign_variant = ProductVariant.objects.create(product=other, sku='OTHER', price=1)
        form = PhotoDetailsForm({'alt_text': 'Wurm', 'sort_order': 0, 'variant': foreign_variant.pk}, instance=photo)
        self.assertFalse(form.is_valid())
        self.assertIn('variant', form.errors)
        form = PhotoDetailsForm({'alt_text': 'Wurm', 'sort_order': 0, 'variant': self.variant.pk}, instance=photo)
        self.assertTrue(form.is_valid())
        form.save()
        photo.refresh_from_db()
        self.assertEqual(photo.variant, self.variant)

    def test_receipt_prefers_independent_artwork_and_centers_continue_action(self):
        StoreBranding.objects.create(thank_you_image_bucket='rotten.world',
            thank_you_image_key='store/products/branding/thanks.png', thank_you_image_alt='A happy Wurm',
            footer_image_bucket='rotten.world', footer_image_key='store/products/branding/site-footer.png')
        with patch('dwiest.django.demos.store.media.s3_client') as s3:
            s3.return_value.generate_presigned_url.side_effect = lambda operation, Params, **kw: 'https://signed.example/' + Params['Key']
            order = self.place()
            response = self.client.get(self.url('order_complete', order.token))
        self.assertContains(response, 'class="wurm-thanks" src="https://signed.example/store/products/branding/thanks.png"')
        self.assertContains(response, 'alt="A happy Wurm"')
        self.assertContains(response, 'class="order-thanks-actions"')
        self.assertContains(response, 'class="button order-continue"')
