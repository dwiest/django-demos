from io import StringIO
from unittest.mock import patch

from django.core import mail
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.test import TestCase, override_settings

from .media import permanent_url, photo_url, record_photo_version
from .models import ProductPhoto, ProductPhotoVersion, StoreBranding
from .orders import notify
from .test_orders import OrderTests
from .test_photos import PhotoTests, image_upload


# Reuse setup/checkout helpers without inheriting and rerunning the existing test suites.
@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
                   STORE_MEDIA_PUBLIC_BASE_URL='https://media.example.com', STORE_MEDIA_BUCKET='rotten.world')
class EmailMediaTests(TestCase):
    def setUp(self):
        OrderTests.setUp(self)
        signer = patch('dwiest.django.demos.store.media.s3_client')
        self.addCleanup(signer.stop)
        signer.start().return_value.generate_presigned_url.return_value = 'https://signed.example/image'

    url = OrderTests.url
    place = OrderTests.place

    def test_receipt_snapshots_option_image_and_survives_catalog_deletion(self):
        generic = ProductPhoto.objects.create(product=self.variant.product, bucket='rotten.world',
                                               key='store/products/generic.png', width=100, height=100)
        selected = ProductPhoto.objects.create(product=self.variant.product, variant=self.variant,
                                              bucket='rotten.world', key='store/products/gray v1.png',
                                              alt_text='Gray Wurm', width=100, height=100)
        record_photo_version(selected)
        order = self.place()
        item = order.items.get()
        self.assertEqual(item.image_ke…7715 tokens truncated…email', order.pk)).status_code, 405)
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
        self.assertContains(response, 'class="order-thanks-image" src="https://signed.example/store/products/branding/thanks.png"')
        self.assertContains(response, 'alt="A happy Wurm"')
        self.assertContains(response, 'class="order-thanks-actions"')
        self.assertContains(response, 'class="button order-continue"')


    def test_receipt_defaults_are_generic_and_store_copy_is_configurable(self):
        order = self.place()
        url = self.url('order_complete', order.token)
        response = self.client.get(url)
        for text in ['Thank you for your order!', 'Your order has been received.', 'Continue shopping']:
            self.assertContains(response, text)
        self.assertNotContains(response, 'Wurm thanks you')
        self.assertNotContains(response, 'surface dweller')
        self.assertNotContains(response, 'RottenWorld Wurm')
        StoreBranding.objects.create(name='Rotten.World', thank_you_heading='Wurm thanks you for your order!',
            thank_you_message='“You have excellent taste. For a surface dweller.”\n<script>unsafe</script>',
            thank_you_button_label='Continue exploring')
        response = self.client.get(url)
        for text in ['Wurm thanks you for your order!', 'surface dweller', 'Continue exploring', '&lt;script&gt;unsafe&lt;/script&gt;']:
            self.assertContains(response, text)
        self.assertNotContains(response, '<script>unsafe</script>')
        StoreBranding.objects.update(thank_you_message='')
        self.assertNotContains(self.client.get(url), 'surface dweller')
