from decimal import Decimal
from io import StringIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.management import call_command
from django.test import Client, TestCase
from django.urls import reverse

from .cart import KEY
from .models import Catalog, Product, ProductVariant, StoreBranding


class StoreTests(TestCase):
    def setUp(self):
        self.catalog = Catalog.objects.create(name='Hats', slug='hats', published=True)
        self.product = Product.objects.create(name='Hat', slug='hat', published=True)
        self.product.catalogs.add(self.catalog)
        self.variant = ProductVariant.objects.create(product=self.product, name='Black', sku='HAT', price='25.10')
        self.other = Product.objects.create(name='Pin', slug='pin', published=True)
        self.other_variant = ProductVariant.objects.create(product=self.other, sku='PIN', price='9.00')
        self.draft = Product.objects.create(name='Draft', slug='draft')
        self.customer = get_user_model().objects.create_user(username='customer', password='test')
        self.manager = get_user_model().objects.create_user(username='manager', password='test')
        self.manager.user_permissions.set(Permission.objects.filter(content_type__app_label='demo_store'))

    def url(self, name, *args):
        return reverse('demos:store:'+name, args=args)

    def add(self, quantity=1, variant=None):
        return self.client.post(self.url('add', self.product.slug), {
            'variant': (variant or self.variant).pk, 'quantity': quantity})

    def test_browsing_catalog_filter_and_draft_visibility(self):
        response = self.client.get(self.url('home'))
        self.assertContains(response, 'Hat')
        self.assertNotContains(response, 'Draft')
        response = self.client.get(self.url('catalog', 'hats'))
        self.assertContains(response, 'Hat')
        self.assertNotContains(response, '>Pin</h2>')
        self.assertEqual(self.client.get(self.url('product', 'draft')).status_code, 404)
        self.catalog.published = False
        self.catalog.save()
        self.assertEqual(self.client.get(self.url('catalog', 'hats')).status_code, 404)

    def test_cart_add_update_remove_and_session_isolation(self):
        self.add(2)
        self.add(1)
        response = self.client.get(self.url('cart'))
        self.assertEqual(response.context['cart_count'], 3)
        self.assertEqual(response.context['cart_total'], Decimal('75.30'))
        self.assertContains(response, 'Checkout')
        self.assertContains(Client().get(self.url('cart')), 'Your cart is empty')
        self.client.post(self.url('update', self.variant.pk), {'quantity': 4})
        self.assertEqual(self.client.session[KEY][str(self.variant.pk)], 4)
        self.client.post(self.url('update', self.variant.pk), {'action': 'remove'})
        self.assertEqual(self.client.session[KEY], {})

    def test_server_price_and_product_variant_validation(self):
        self.add(1, self.other_variant)
        self.assertNotIn(KEY, self.client.session)
        self.client.post(self.url('add', 'hat'), {'variant': self.variant.pk, 'quantity': 2, 'price': '0.01'})
        response = self.client.get(self.url('cart'))
        self.assertEqual(response.context['cart_total'], Decimal('50.20'))
        self.variant.price = Decimal('30.00')
        self.variant.save()
        self.assertEqual(self.client.get(self.url('cart')).context['cart_total'], Decimal('60.00'))

    def test_invalid_quantities_cannot_change_cart(self):
        for quantity in [0, -1, 100, 'abc', '1.5']:
            self.add(quantity)
            self.assertNotIn(KEY, self.client.session)
        self.add(99)
        self.assertContains(self.add(), 'up to 99')
        self.assertEqual(self.client.session[KEY][str(self.variant.pk)], 99)
        for quantity in [0, -1, 100, 'abc']:
            response = self.client.post(self.url('update', self.variant.pk), {'quantity': quantity})
            self.assertContains(response, 'Enter a whole quantity')
            self.assertEqual(self.client.session[KEY][str(self.variant.pk)], 99)

    def test_unavailable_cart_items_are_removed(self):
        self.add()
        self.variant.active = False
        self.variant.save()
        self.assertContains(self.client.get(self.url('cart')), 'Your cart is empty')
        self.assertEqual(self.client.session[KEY], {})
        self.variant.active = True
        self.variant.save()
        self.add()
        self.product.published = False
        self.product.save()
        self.assertContains(self.client.get(self.url('cart')), 'Your cart is empty')

    def test_mutations_require_post_and_csrf(self):
        self.assertEqual(self.client.get(self.url('add', 'hat')).status_code, 405)
        self.assertEqual(self.client.get(self.url('update', self.variant.pk)).status_code, 405)
        strict = Client(enforce_csrf_checks=True)
        self.assertEqual(strict.post(self.url('add', 'hat'), {'variant': self.variant.pk, 'quantity': 1}).status_code, 403)

    def test_management_requires_permissions_even_for_staff(self):
        paths = [self.url('manage'), self.url('product_create'), self.url('product_edit', self.product.pk),
                 self.url('catalog_create'), self.url('catalog_edit', self.catalog.pk)]
        for user in [None, self.customer]:
            if user:
                user.is_staff = True
                user.save()
                self.client.force_login(user)
            for path in paths:
                self.assertEqual(self.client.get(path).status_code, 403)
                self.assertEqual(self.client.post(path, {}).status_code, 403)
        self.client.force_login(self.manager)
        for path in paths:
            self.assertEqual(self.client.get(path).status_code, 200)

    def test_manager_can_create_product_and_variants(self):
        self.client.force_login(self.manager)
        response = self.client.post(self.url('product_create'), {
            'name': 'Poster', 'slug': 'poster', 'description': 'Wall art', 'published': 'on',
            'catalogs': [self.catalog.pk],
            'variants-TOTAL_FORMS': '2', 'variants-INITIAL_FORMS': '0',
            'variants-MIN_NUM_FORMS': '1', 'variants-MAX_NUM_FORMS': '1000',
            'variants-0-name': 'Small', 'variants-0-sku': 'POSTER-S', 'variants-0-price': '10.00', 'variants-0-active': 'on', 'variants-0-fulfillment_method': 'pod',
            'variants-1-name': 'Large', 'variants-1-sku': 'POSTER-L', 'variants-1-price': '20.00', 'variants-1-active': 'on', 'variants-1-fulfillment_method': 'pod',
        })
        self.assertRedirects(response, self.url('manage'))
        self.assertEqual(Product.objects.get(slug='poster').variants.count(), 2)
        response = self.client.post(self.url('catalog_create'), {'name': 'Art', 'slug': 'art', 'published': 'on'})
        self.assertRedirects(response, self.url('manage'))
        self.assertTrue(Catalog.objects.get(slug='art').published)

    def test_seed_is_repeatable_and_preserves_edits(self):
        Product.objects.all().delete()
        call_command('seed_store', stdout=StringIO())
        hat = Product.objects.get(slug='oddment-hat')
        hat.name = 'My edited hat'
        hat.save()
        count = ProductVariant.objects.count()
        call_command('seed_store', stdout=StringIO())
        hat.refresh_from_db()
        self.assertEqual(hat.name, 'My edited hat')
        self.assertEqual(ProductVariant.objects.count(), count)
        group = Group.objects.get(name='Shop administrators')
        self.assertTrue(group.permissions.filter(codename='change_product').exists())

    def test_navigation_home_card_and_html_escaping(self):
        response = self.client.get(reverse('demos:home'))
        self.assertContains(response, 'Open Store')
        self.assertContains(response, self.url('home'))
        self.product.name = '<script>alert(1)</script>'
        self.product.save()
        response = self.client.get(self.url('product', 'hat'))
        self.assertContains(response, '&lt;script&gt;')
        self.assertNotContains(response, '<script>alert(1)</script>')

    def test_quick_add_preserves_catalog_and_cart_validation(self):
        response = self.client.post(self.url('add', 'hat'), {
            'variant': self.variant.pk, 'quantity': 1, 'quick_add': '1', 'catalog': 'hats'})
        self.assertRedirects(response, self.url('catalog', 'hats'))
        self.assertEqual(self.client.session[KEY][str(self.variant.pk)], 1)
        response = self.client.post(self.url('add', 'hat'), {
            'variant': self.other_variant.pk, 'quantity': 1, 'quick_add': '1'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.session[KEY], {str(self.variant.pk): 1})
        response = self.client.post(self.url('add', 'hat'), {
            'variant': self.variant.pk, 'quantity': 1, 'quick_add': '1', 'catalog': 'https://example.com'})
        self.assertRedirects(response, self.url('home'))
        self.assertEqual(self.client.session[KEY][str(self.variant.pk)], 2)

    def test_quick_add_shows_only_active_variants(self):
        other = ProductVariant.objects.create(product=self.product, sku='HAT2', name='Green', price='30.00')
        inactive = ProductVariant.objects.create(product=self.product, sku='HAT3', name='Unavailable color', price='15.00', active=False)
        response = self.client.get(self.url('home'))
        self.assertContains(response, 'Select an option')
        self.assertContains(response, 'Green · $30.00')
        self.assertNotContains(response, 'Unavailable color')
        self.client.post(self.url('add', 'hat'), {'variant': inactive.pk, 'quantity': 1, 'quick_add': '1'})
        self.assertNotIn(KEY, self.client.session)
        self.client.post(self.url('add', 'hat'), {'variant': other.pk, 'quantity': 1, 'quick_add': '1'})
        self.assertEqual(self.client.session[KEY][str(other.pk)], 1)

    def test_category_get_form_preserves_other_filters(self):
        response = self.client.get(self.url('home'), {
            'category': 'hats', 'q': 'Hat', 'sort': 'price_desc',
        })
        self.assertEqual([p.pk for p in response.context['products']], [self.product.pk])
        self.assertEqual(response.context['sort'], 'price_desc')
        self.assertContains(response, 'name="category"')
        self.assertNotContains(response, 'onchange=')

    def test_all_products_overrides_catalog_path(self):
        response = self.client.get(self.url('catalog', 'hats'), {'category': ''})
        self.assertIsNone(response.context['catalog'])
        self.assertEqual(len(response.context['products']), 2)

    def test_status_visibility_setting_preserves_purchase_rules(self):
        branding = StoreBranding.objects.create(pk=1, show_item_status=False)
        self.variant.fulfillment_method = 'stock'
        self.variant.save()
        for name, args in [('home', ()), ('catalog', ('hats',)), ('product', ('hat',))]:
            response = self.client.get(self.url(name, *args))
            self.assertNotContains(response, 'class="store-availability"')
            self.assertNotContains(response, ' · Sold out')
            self.assertNotContains(response, 'Demo checkout available')
            self.assertContains(response, 'disabled')
        response = self.add()
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(str(self.variant.pk), self.client.session.get(KEY, {}))
        branding.show_item_status = True
        branding.save()
        response = self.client.get(self.url('product', 'hat'))
        self.assertContains(response, 'class="store-availability"')
        self.assertContains(response, ' · Sold out')
