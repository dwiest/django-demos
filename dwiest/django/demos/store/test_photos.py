from io import BytesIO, StringIO
from unittest.mock import patch
from urllib.parse import urlparse, parse_qs

from botocore.exceptions import ClientError
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from PIL import Image

from .forms import PhotoUploadForm
from .media import MAX_BYTES, prepare_image, s3_client
from .models import Product, ProductPhoto


def image_upload(name='photo.png', image_format='PNG'):
    output = BytesIO()
    Image.new('RGB', (32, 24), 'coral').save(output, format=image_format)
    return SimpleUploadedFile(name, output.getvalue(), content_type='application/octet-stream')


class PhotoTests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(name='Hat', slug='hat', published=True)
        self.other = Product.objects.create(name='Other', slug='other', published=True)
        self.manager = get_user_model().objects.create_user(username='manager')
        self.manager.user_permissions.set(Permission.objects.filter(content_type__app_label='demo_store'))
        self.client.force_login(self.manager)
        self.s3_patch = patch('dwiest.django.demos.store.media.s3_client')
        self.s3 = self.s3_patch.start().return_value
        self.s3.generate_presigned_url.side_effect = lambda operation, Params, **kwargs: 'https://s3.example/'+Params['Key']
        self.addCleanup(self.s3_patch.stop)

    def url(self, name, *args):
        return reverse('demos:store:'+name, args=args)

    def photo(self, **kwargs):
        defaults = dict(product=self.product, bucket='rotten.world', key='store/products/1/test.png', width=32, height=24)
        defaults.update(kwargs)
        return ProductPhoto.objects.create(**defaults)

    def test_multiple_uploads_write_s3_objects_and_metadata(self):
        response = self.client.post(self.url('photo_upload', self.product.pk), {
            'photos': [image_upload('front.png'), image_upload('back.jpg', 'JPEG')]})
        self.assertRedirects(response, self.url('product_edit', self.product.pk))
        photos = list(self.product.photos.all())
        self.assertEqual(len(photos), 2)
        self.assertEqual([p.sort_order for p in photos], [0, 1])
        self.assertEqual(self.s3.put_object.call_count, 2)
        self.assertNotEqual(photos[0].key, photos[1].key)
        self.assertTrue(photos[0].key.startswith('store/products/{}/'.format(self.product.pk)))
        for photo, call in zip(photos, self.s3.put_object.call_args_list):
            self.assertEqual(photo.bucket, 'rotten.world')
            self.assertEqual((photo.width, photo.height), (32, 24))
            self.assertEqual(call.kwargs['Bucket'], photo.bucket)
            self.assertEqual(call.kwargs['Key'], photo.key)
            self.assertNotIn('ACL', call.kwargs)
            self.assertIn(call.kwargs['ContentType'], ['image/png', 'image/jpeg'])
            Image.open(BytesIO(call.kwargs['Body'])).verify()
        self.assertNotIn('data', {field.name for field in ProductPhoto._meta.fields})

    def test_every_file_validated_before_any_s3_write(self):
        response = self.client.post(self.url('photo_upload', self.product.pk), {
            'photos': [image_upload(), SimpleUploadedFile('not.png', b'<script>bad</script>')]})
        self.assertContains(response, 'valid JPEG, PNG, or WebP')
        self.s3.put_object.assert_not_called()
        self.assertEqual(ProductPhoto.objects.count(), 0)
        self.assertContains(self.client.post(self.url('photo_upload', self.product.pk), {}), 'Select at least one photo')

    def test_limits_and_svg_rejection(self):
        form = PhotoUploadForm(files={'photos': []})
        # Exercise the field separately: the request widget uses MultiValueDict.getlist.
        field = form.fields['photos']
        with self.assertRaises(ValidationError):
            field.clean([image_upload() for _ in range(11)])
        with self.assertRaises(ValidationError):
            prepare_image(SimpleUploadedFile('x.svg', b'<svg xmlns="http://www.w3.org/2000/svg"/>'))
        large = image_upload()
        large.size = MAX_BYTES + 1
        with self.assertRaises(ValidationError):
            prepare_image(large)
        with patch('dwiest.django.demos.store.media.MAX_PIXELS', 10):
            with self.assertRaises(ValidationError):
                prepare_image(image_upload())

    def test_failed_batch_rolls_back_metadata_and_cleans_uploaded_objects(self):
        self.s3.put_object.side_effect = [None, ClientError({'Error': {'Code': 'AccessDenied'}}, 'PutObject')]
        with self.assertLogs('dwiest.django.demos.store.views', level='ERROR'):
            response = self.client.post(self.url('photo_upload', self.product.pk), {
                'photos': [image_upload(), image_upload()]})
        self.assertContains(response, 'Photos could not be saved')
        self.assertEqual(ProductPhoto.objects.count(), 0)
        self.s3.delete_object.assert_called_once()

    def test_gallery_cover_order_alt_text_and_legacy_fallback(self):
        first = self.photo(sort_order=5, alt_text='Hat front')
        second = self.photo(key='store/products/1/back.png', sort_order=1, alt_text='Hat back')
        self.assertEqual(self.product.cover_photo, second)
        response = Client().get(self.url('product', self.product.slug))
        self.assertContains(response, 'Hat front')
        self.assertContains(response, 'Hat back')
        self.assertContains(response, 'data-photo-link', count=2)
        self.assertContains(response, 'store/gallery.js')
        response = Client().get(self.url('home'))
        self.assertContains(response, 'alt="Hat back"')
        self.assertNotContains(response, 'alt="Hat front"')
        self.client.post(self.url('photo_edit', self.product.pk, first.pk), {'alt_text': 'New alt', 'sort_order': 0})
        self.assertEqual(self.product.cover_photo.pk, first.pk)
        first.refresh_from_db()
        self.assertEqual(first.alt_text, 'New alt')
        ProductPhoto.objects.all().delete()
        self.product.image_url = 'https://legacy.example/hat.png'
        self.product.save()
        self.assertContains(Client().get(self.url('home')), self.product.image_url)

    def test_remove_and_product_cascade_delete_clean_up_after_commit(self):
        photo = self.photo()
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(self.url('photo_delete', self.product.pk, photo.pk))
            self.s3.delete_object.assert_not_called()
        self.s3.delete_object.assert_called_once_with(Bucket=photo.bucket, Key=photo.key)
        self.assertFalse(ProductPhoto.objects.exists())
        self.s3.delete_object.reset_mock()
        self.photo()
        with self.captureOnCommitCallbacks(execute=True):
            self.product.delete()
        self.s3.delete_object.assert_called_once()

    def test_remove_cleanup_failure_is_logged_without_crashing(self):
        photo = self.photo()
        self.s3.delete_object.side_effect = RuntimeError('S3 unavailable')
        with self.assertLogs('dwiest.django.demos.store.media', level='ERROR'):
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(self.url('photo_delete', self.product.pk, photo.pk))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(ProductPhoto.objects.exists())

    def test_photos_cannot_be_changed_through_another_product(self):
        photo = self.photo()
        for name, data in [('photo_edit', {'alt_text': 'tampered', 'sort_order': 0}), ('photo_delete', {})]:
            response = self.client.post(self.url(name, self.other.pk, photo.pk), data)
            self.assertEqual(response.status_code, 404)
        self.s3.delete_object.assert_not_called()

    def test_permission_checks_and_post_only(self):
        photo = self.photo()
        urls = [self.url('photo_upload', self.product.pk), self.url('photo_edit', self.product.pk, photo.pk),
                self.url('photo_delete', self.product.pk, photo.pk)]
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 405)
        self.client.logout()
        for url in urls:
            self.assertEqual(self.client.post(url, {}).status_code, 403)
        staff = get_user_model().objects.create_user(username='staff', is_staff=True)
        self.client.force_login(staff)
        for url in urls:
            self.assertEqual(self.client.post(url, {}).status_code, 403)
        self.s3.put_object.assert_not_called()
        self.s3.delete_object.assert_not_called()

    def test_csrf_and_management_multipart_form(self):
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.manager)
        self.assertEqual(strict.post(self.url('photo_upload', self.product.pk), {'photos': image_upload()}).status_code, 403)
        response = self.client.get(self.url('product_edit', self.product.pk))
        self.assertContains(response, 'enctype="multipart/form-data"')
        self.assertContains(response, 'multiple')
        self.assertContains(response, 'Product photos')

    def test_invalid_metadata_preserves_existing_values(self):
        photo = self.photo()
        response = self.client.post(self.url('photo_edit', self.product.pk, photo.pk), {'sort_order': -1})
        self.assertEqual(response.status_code, 200)
        photo.refresh_from_db()
        self.assertEqual(photo.sort_order, 0)

    def test_seed_updates_manager_group_with_new_permissions(self):
        call_command('seed_store', stdout=StringIO())
        from django.contrib.auth.models import Group
        self.assertTrue(Group.objects.get(name='Shop administrators').permissions.filter(codename='add_productphoto').exists())


class S3ConfigurationTests(TestCase):
    @override_settings(STORE_MEDIA_REGION='us-east-1', STORE_MEDIA_URL_TTL=120)
    def test_real_sdk_signs_private_dotted_bucket_url_without_network(self):
        with patch.dict('os.environ', {'AWS_ACCESS_KEY_ID': 'test', 'AWS_SECRET_ACCESS_KEY': 'test',
                                      'AWS_EC2_METADATA_DISABLED': 'true'}):
            client = s3_client()
            self.assertEqual(client.meta.config.s3['addressing_style'], 'path')
            url = client.generate_presigned_url('get_object', Params={'Bucket': 'rotten.world', 'Key': 'store/products/a.png'}, ExpiresIn=120)
            parsed = urlparse(url)
            self.assertNotIn('rotten.world.', parsed.netloc)
            self.assertIn('/rotten.world/store/products/a.png', parsed.path)
            self.assertEqual(parse_qs(parsed.query)['X-Amz-Expires'], ['120'])
