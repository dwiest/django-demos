from unittest.mock import patch
from io import StringIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.management import call_command
from django.test import Client, TestCase
from django.urls import reverse

from .models import Product, ProductPhoto, StoreBranding
from .test_photos import image_upload


class BrandingTests(TestCase):
    def setUp(self):
        self.manager = get_user_model().objects.create_user(username='manager')
        self.manager.user_permissions.set(Permission.objects.filter(content_type__app_label='demo_store'))
        self.client.force_login(self.manager)
        self.s3_patch = patch('dwiest.django.demos.store.media.s3_client')
        self.s3 = self.s3_patch.start().return_value
        self.s3.generate_presigned_url.side_effect = lambda op, Params, **kw: 'https://s3.example/'+Params['Key']
        self.addCleanup(self.s3_patch.stop)
        self.url = reverse('demos:store:branding')
        self.data = {'shipping_rate': '6.95', 'shipping_estimate': '', 'name': 'My store', 'tagline': 'Unexpected finds', 'introduction': 'Welcome here',
                     'footer_heading': 'Stay curious', 'footer_text': 'Made for you',
                     'contact_email': 'hello@example.com', 'footer_link_label': 'About',
                     'footer_link_url': 'https://example.com/about', 'copyright_text': 'All ours', 'coupon_code': 'DISCOUNT', 'coupon_percent': '5'}

    def test_default_standalone_shell_on_store_pages(self):
        for name in ['home', 'cart', 'manage', 'branding', 'product_create']:
            response = self.client.get(reverse('demos:store:'+name))
            self.assertContains(response, 'Oddment Supply')
            self.assertNotContains(response, 'RottenWorld')
            self.assertNotContains(response, 'Django Demos')
            self.assertNotContains(response, 'ww-site-header')
            self.assertContains(response, 'class="store-footer"', count=1)
            self.assertContains(response, 'Store settings')

    def test_configuration_saves_and_displays_without_changing_products(self):
        product = Product.objects.create(name='My existing merchandise', slug='existing')
        self.assertRedirects(self.client.post(self.url, self.data), reverse('demos:store:home'))
        response = Client().get(reverse('demos:store:home'))
        for text in ['My store', 'Unexpected finds', 'Welcome here', 'Stay curious', 'Made for you', 'hello@example.com', 'https://example.com/about', 'All ours']:
            self.assertContains(response, text)
        product.refresh_from_db()
        self.assertEqual(product.name, 'My existing merchandise')
        self.client.post(self.url, {**self.data, 'name': 'Updated name'})
        self.assertEqual(StoreBranding.objects.count(), 1)
        self.assertEqual(StoreBranding.objects.get().name, 'Updated name')

    def test_uploaded_images_use_s3_and_retain_replaced_objects(self):
        response = self.client.post(self.url, {**self.data, 'header_image': image_upload(), 'footer_image': image_upload()})
        self.assertEqual(response.status_code, 302)
        branding = StoreBranding.objects.get()
        self.assertEqual(self.s3.put_object.call_count, 2)
        self.assertIn('/branding/', branding.header_image_key)
        response = self.client.get(reverse('demos:store:home'))
        self.assertContains(response, branding.header_image_key)
        self.assertContains(response, branding.footer_image_key)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(self.url, {**self.data, 'remove_header_image': 'on'})
            self.s3.delete_object.assert_not_called()
        self.s3.delete_object.assert_not_called()
        branding.refresh_from_db()
        self.assertEqual(branding.header_image_key, '')
        self.assertNotEqual(branding.footer_image_key, '')

    def test_permissions_and_csrf(self):
        customer = get_user_model().objects.create_user(username='customer', is_staff=True)
        self.assertEqual(Client().post(self.url, self.data).status_code, 403)
        self.client.force_login(customer)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(self.client.post(self.url, self.data).status_code, 403)
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.manager)
        self.assertEqual(strict.post(self.url, self.data).status_code, 403)
        self.s3.put_object.assert_not_called()

    def test_invalid_images_and_links_do_not_save(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        for changes in [{'header_image': SimpleUploadedFile('bad.svg', b'<svg/>')},
                        {'footer_link_url': 'javascript:alert(1)'},
                        {'footer_link_label': ''},
                        {'header_image': image_upload(), 'remove_header_image': 'on'}]:
            response = self.client.post(self.url, {**self.data, **changes})
            self.assertEqual(response.status_code, 200)
            self.assertFalse(StoreBranding.objects.exists())
        self.s3.put_object.assert_not_called()

    def test_failed_image_batch_preserves_old_branding_and_cleans_new_objects(self):
        StoreBranding.objects.create(name='Existing')
        self.s3.put_object.side_effect = [None, RuntimeError('unavailable')]
        with self.assertLogs('dwiest.django.demos.store.views', level='ERROR'):
            response = self.client.post(self.url, {**self.data, 'header_image': image_upload(), 'footer_image': image_upload()})
        self.assertContains(response, 'could not be saved')
        self.assertEqual(StoreBranding.objects.get().name, 'Existing')
        self.s3.delete_object.assert_called_once()

    def test_store_copy_escapes_html(self):
        self.client.post(self.url, {**self.data, 'footer_text': '<script>bad()</script>'})
        response = self.client.get(reverse('demos:store:home'))
        self.assertContains(response, '&lt;script&gt;')
        self.assertNotContains(response, '<script>bad()</script>')

    def test_card_choices_use_only_zero_order_photos_and_keep_detail_gallery(self):
        product = Product.objects.create(name='Hat', slug='hat', published=True)
        for order, label in [(0, 'Black'), (0, 'Gray'), (1, 'Back')]:
            ProductPhoto.objects.create(product=product, bucket='rotten.world', key='store/products/'+label,
                                        alt_text=label, sort_order=order, width=32, height=24)
        response = self.client.get(reverse('demos:store:home'))
        self.assertContains(response, 'data-card-photo', count=2)
        self.assertContains(response, 'data-alt="Black"')
        self.assertContains(response, 'data-alt="Gray"')
        self.assertNotContains(response, 'data-alt="Back"')
        response = self.client.get(reverse('demos:store:product', args=['hat']))
        self.assertContains(response, 'data-photo-link', count=3)
        product.photos.filter(sort_order=0).update(sort_order=2)
        response = self.client.get(reverse('demos:store:home'))
        self.assertNotContains(response, 'data-card-photo')
        self.assertEqual(len(product.featured_photos), 1)

    def test_permission_refresh_does_not_add_sample_products_to_populated_store(self):
        Product.objects.create(name='My catalog', slug='mine')
        call_command('seed_store', stdout=StringIO())
        self.assertEqual(Product.objects.count(), 1)
        from django.contrib.auth.models import Group
        self.assertTrue(Group.objects.get(name='Shop administrators').permissions.filter(codename='change_storebranding').exists())


    def test_email_artwork_upload_replace_remove_retains_original(self):
        self.client.post(self.url, {**self.data, 'email_header_image': image_upload(),
                                  'email_footer_image': image_upload()})
        branding = StoreBranding.objects.get()
        original = branding.email_header_image_key
        self.assertTrue(original)
        self.assertTrue(branding.email_footer_image_key)
        self.assertEqual(branding.header_image_key, '')
        self.client.post(self.url, {**self.data, 'email_header_image': image_upload()})
        branding.refresh_from_db()
        self.assertNotEqual(branding.email_header_image_key, original)
        self.client.post(self.url, {**self.data, 'remove_email_footer_image': 'on'})
        branding.refresh_from_db()
        self.assertEqual(branding.email_footer_image_key, '')
        self.s3.delete_object.assert_not_called()

    def test_independent_thank_you_artwork_is_uploaded_and_retained(self):
        response = self.client.post(self.url, {**self.data, 'thank_you_image': image_upload(),
                                               'thank_you_image_alt': 'Wurm celebrating'})
        self.assertEqual(response.status_code, 302)
        branding = StoreBranding.objects.get()
        original = branding.thank_you_image_key
        self.assertTrue(original)
        self.assertEqual(branding.footer_image_key, '')
        self.assertEqual(branding.email_footer_image_key, '')
        self.client.post(self.url, {**self.data, 'remove_thank_you_image': 'on'})
        branding.refresh_from_db()
        self.assertEqual(branding.thank_you_image_key, '')
        self.s3.delete_object.assert_not_called()


    def test_thank_you_copy_saves_through_store_settings(self):
        response = self.client.post(self.url, {**self.data,
            'thank_you_heading': 'Wurm thanks you for your order!',
            'thank_you_message': 'For a surface dweller, you have excellent taste.',
            'thank_you_button_label': 'Continue exploring'})
        self.assertEqual(response.status_code, 302)
        branding = StoreBranding.objects.get()
        self.assertEqual(branding.thank_you_heading, 'Wurm thanks you for your order!')
        self.assertIn('surface dweller', branding.thank_you_message)
        self.assertEqual(branding.thank_you_button_label, 'Continue exploring')
        self.client.post(self.url, {**self.data, 'thank_you_heading': '', 'thank_you_message': '',
                                   'thank_you_button_label': ''})
        branding.refresh_from_db()
        self.assertEqual(branding.thank_you_heading, 'Thank you for your order!')
        self.assertEqual(branding.thank_you_button_label, 'Continue shopping')
        self.assertEqual(branding.thank_you_message, '')
