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
        self.assertEqual(item.image_key, selected.key)
        html = mail.outbox[-1].alternatives[0][0]
        self.assertIn('https://media.example.com/store/products/gray%20v1.png', html)
        self.assertIn('width="56"', html)
        self.assertNotIn('generic.png', html)
        self.assertIn('Thanks for your order!', html)
        selected.key = 'store/products/gray-v2.png'
        selected.save()
        with patch('dwiest.django.demos.store.media.s3_client') as s3:
            self.variant.product.delete()
            s3.assert_not_called()
        item.refresh_from_db()
        self.assertIsNone(item.variant_id)
        self.assertEqual(item.email_image_url, 'https://media.example.com/store/products/gray%20v1.png')
        self.assertTrue(ProductPhotoVersion.objects.filter(photo__isnull=True, key=item.image_key).exists())
        event = order.events.create(message='An update')
        notify(event.pk)
        self.assertIn(item.email_image_url, mail.outbox[-1].alternatives[0][0])
        self.assertNotIn('Thanks for your order!', mail.outbox[-1].alternatives[0][0])

    def test_no_wrong_variant_fallback_and_no_expiring_links(self):
        from .models import ProductVariant
        other = ProductVariant.objects.create(product=self.variant.product, name='Other', price=1, sku='OTHER')
        ProductPhoto.objects.create(product=self.variant.product, variant=other, bucket='rotten.world',
                                    key='wrong-option.png', width=100, height=100)
        with override_settings(STORE_MEDIA_PUBLIC_BASE_URL=''):
            with patch('dwiest.django.demos.store.media.s3_client') as s3:
                order = self.place()
                self.assertEqual(order.items.get().image_key, '')
                self.assertNotIn('<img', mail.outbox[-1].alternatives[0][0])
                s3.return_value.generate_presigned_url.reset_mock()
                notify(order.events.create(message="Update").pk)
                s3.return_value.generate_presigned_url.assert_not_called()

    def test_email_artwork_links_escaping_and_status_headings(self):
        StoreBranding.objects.create(name='Rotten.World', email_header_image_bucket='rotten.world',
            email_header_image_key='store/products/branding/header-v1.png',
            email_footer_image_bucket='rotten.world', email_footer_image_key='store/products/branding/footer-v1.png',
            email_footer_heading='Good stuff. Questionable influences.', email_footer='<script>unsafe</script>',
            email_shop_url='https://rotten.world/', email_help_url='https://rotten.world/help/',
            contact_email='support@example.com')
        order = self.place()
        message = mail.outbox[-1]
        html = message.alternatives[0][0]
        for value in ['header-v1.png', 'footer-v1.png', 'Questionable influences.', 'https://rotten.world/help/',
                      'mailto:support@example.com', '&lt;script&gt;unsafe&lt;/script&gt;']:
            self.assertIn(value, html)
        self.assertNotIn('<script>', html)
        self.assertEqual(message.attachments, [])
        self.assertNotIn('X-Amz', html)
        self.assertIn('support@example.com', message.body)
        for status, heading in [('fulfilled', 'Your order has shipped!'), ('cancelled', 'Your order was cancelled')]:
            order.status = status
            order.save()
            notify(order.events.create(message='Updated').pk)
            updated = mail.outbox[-1].alternatives[0][0]
            self.assertIn(heading, updated)
            self.assertNotIn('We’ll email you when your order ships.', updated)


class PhotoVersionTests(TestCase):
    setUp = PhotoTests.setUp
    url = PhotoTests.url
    photo = PhotoTests.photo

    def test_replace_restore_and_retain_history(self):
        photo = self.photo()
        old_key = photo.key
        response = self.client.post(self.url('photo_edit', self.product.pk, photo.pk),
            {'alt_text': 'New', 'sort_order': 0, 'replacement_image': image_upload()})
        self.assertEqual(response.status_code, 302)
        photo.refresh_from_db()
        self.assertEqual(photo.version, 2)
        self.assertNotEqual(photo.key, old_key)
        self.assertEqual(list(photo.versions.values_list('version', flat=True)), [2, 1])
        self.s3.delete_object.assert_not_called()
        url = self.url('photo_restore', self.product.pk, photo.pk, 1)
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertEqual(self.client.post(url).status_code, 302)
        photo.refresh_from_db()
        self.assertEqual(photo.version, 3)
        self.assertEqual(photo.key, old_key)
        self.assertEqual(photo.versions.count(), 3)
        self.assertEqual(self.client.post(self.url('photo_restore', self.other.pk, photo.pk, 1)).status_code, 404)
        self.client.logout()
        self.assertEqual(self.client.post(url).status_code, 403)

    def test_failed_replacement_preserves_current_and_history(self):
        photo = self.photo()
        record_photo_version(photo)
        self.s3.put_object.side_effect = RuntimeError('S3 unavailable')
        with self.assertLogs('dwiest.django.demos.store.views', level='ERROR'):
            response = self.client.post(self.url('photo_edit', self.product.pk, photo.pk),
                {'alt_text': 'New', 'sort_order': 0, 'replacement_image': image_upload()})
        self.assertContains(response, 'Photo could not be saved')
        photo.refresh_from_db()
        self.assertEqual(photo.version, 1)
        self.assertEqual(photo.versions.count(), 1)


class PermanentURLTests(TestCase):
    @override_settings(STORE_MEDIA_PUBLIC_BASE_URL='https://cdn.example.com/assets/', STORE_MEDIA_BUCKET='rotten.world')
    def test_public_url_quotes_key_and_does_not_sign(self):
        with patch('dwiest.django.demos.store.media.s3_client') as s3:
            photo = ProductPhoto(bucket='rotten.world', key='store/products/a #1.png')
            self.assertEqual(permanent_url(photo.bucket, photo.key), 'https://cdn.example.com/assets/store/products/a%20%231.png')
            self.assertEqual(permanent_url('other-bucket', photo.key), '')
            s3.assert_not_called()
        for base in ['http://example.com', 'https://example.com/?token=abc']:
            with override_settings(STORE_MEDIA_PUBLIC_BASE_URL=base):
                with self.assertRaises(ImproperlyConfigured):
                    permanent_url('rotten.world', photo.key)

    def test_bucket_versioning_is_read_only_unless_explicitly_enabled(self):
        with patch('dwiest.django.demos.store.management.commands.configure_store_media_versioning.s3_client') as factory:
            client = factory.return_value
            client.get_bucket_versioning.return_value = {}
            call_command('configure_store_media_versioning', stdout=StringIO())
            client.put_bucket_versioning.assert_not_called()
            client.get_bucket_versioning.side_effect = [{}, {'Status': 'Enabled'}]
            call_command('configure_store_media_versioning', '--enable', stdout=StringIO())
            client.put_bucket_versioning.assert_called_once_with(Bucket='rotten.world', VersioningConfiguration={'Status': 'Enabled'})


class ImageHistoryMigrationTests(TestCase):
    def test_backfill_records_existing_photo_and_order_snapshot(self):
        # Use the historical migration function with current app models to exercise
        # the data path, independent of the empty test-database schema migration.
        from importlib import import_module
        from django.apps import apps
        from django.db import connection
        from .models import Product, ProductVariant, StoreOrder, ShippingAddress, StoreOrderItem
        product = Product.objects.create(name='Hat', slug='migration-hat')
        variant = ProductVariant.objects.create(product=product, name='Gray', sku='MIGRATE', price=10)
        photo = ProductPhoto.objects.create(product=product, variant=variant, bucket='rotten.world',
                                           key='store/products/old.png', width=32, height=24)
        address = ShippingAddress.objects.create(name='Buyer', line1='Main', city='Raleigh', state='NC', postal_code='27601')
        order = StoreOrder.objects.create(email='buyer@example.com', shipping_address=address,
            subtotal=10, shipping_method='standard', shipping_cost=0, total=10,
            payment_method='card_usd', payment_acknowledgment='SIMULATED')
        item = StoreOrderItem.objects.create(order=order, variant=variant, product_name='Hat',
            variant_name='Gray', sku='MIGRATE', quantity=1, unit_price=10)
        migration = import_module('dwiest.django.demos.store.migrations.0006_email_artwork_photo_versions')
        migration.retain_existing_images(apps, connection.schema_editor())
        self.assertEqual(photo.versions.get().key, photo.key)
        item.refresh_from_db()
        self.assertEqual(item.image_key, photo.key)


class StorefrontURLRegressionTests(TestCase):
    @override_settings(STORE_MEDIA_PUBLIC_BASE_URL='https://s3.amazonaws.com/rotten.world/store/images')
    def test_email_base_never_changes_product_or_site_image_delivery(self):
        from .models import Product
        product = Product.objects.create(name='Wurm', slug='url-regression')
        photo = ProductPhoto(product=product, bucket='rotten.world',
                             key='store/products/2/0f4bda33f2fe4140bbc4a19feeb57b83.png')
        branding = StoreBranding(header_image_bucket='rotten.world', header_image_key='store/products/branding/header.png',
                                footer_image_bucket='rotten.world', footer_image_key='store/products/branding/footer.png')
        with patch('dwiest.django.demos.store.media.s3_client') as factory:
            factory.return_value.generate_presigned_url.side_effect = lambda operation, Params, **kw: 'https://signed.example/' + Params['Key']
            self.assertEqual(photo.url, 'https://signed.example/' + photo.key)
            self.assertEqual(branding.header_image_url, 'https://signed.example/store/products/branding/header.png')
            self.assertEqual(branding.footer_image_url, 'https://signed.example/store/products/branding/footer.png')
            keys = [call.kwargs['Params']['Key'] for call in factory.return_value.generate_presigned_url.call_args_list]
            self.assertEqual(keys, [photo.key, branding.header_image_key, branding.footer_image_key])
        with override_settings(STORE_MEDIA_PUBLIC_BASE_URL='not a valid URL'):
            with patch('dwiest.django.demos.store.media.s3_client') as factory:
                factory.return_value.generate_presigned_url.return_value = 'https://signed.example/image'
                self.assertEqual(photo_url(photo), 'https://signed.example/image')

class S3EmailPathTests(TestCase):
    @override_settings(STORE_MEDIA_BUCKET='rotten.world')
    def test_s3_email_urls_append_exact_stored_key_from_bucket_root(self):
        key = 'store/products/branding/895ef1d1247c46f895428e24192f4c9f.png'
        for base, endpoint in [
            ('https://s3.amazonaws.com/rotten.world/store/images', 's3.amazonaws.com'),
            ('https://s3.us-east-1.amazonaws.com/rotten.world/store/products', 's3.us-east-1.amazonaws.com'),
            ('https://rotten.world.s3.us-east-1.amazonaws.com/store/images', 's3.us-east-1.amazonaws.com'),
        ]:
            with self.subTest(base=base), override_settings(STORE_MEDIA_PUBLIC_BASE_URL=base):
                url = permanent_url('rotten.world', key)
                self.assertEqual(url, 'https://' + endpoint + '/rotten.world/' + key)
                self.assertNotIn('store/images', url)
                self.assertNotIn('X-Amz', url)
