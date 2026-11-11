from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings

from .forms import VariantForm
from .models import Product, ProductVariant, StoreBranding
from .orders import totals
from . import test_orders


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class DiscountTests(TestCase):
    setUp = test_orders.OrderTests.setUp
    url = test_orders.OrderTests.url
    place = test_orders.OrderTests.place

    def test_sale_coupon_shipping_and_order_snapshot(self):
        self.variant.sale_price = Decimal('15.00')
        self.variant.save()
        StoreBranding.objects.create(coupon_code='SAVE', coupon_percent=10,
                                     free_shipping_threshold='27.00')
        self.data['coupon'] = ' save '
        order = self.place()
        self.assertEqual(order.subtotal, Decimal('30.00'))
        self.assertEqual(order.discount, Decimal('3.00'))
        self.assertEqual(order.shipping_cost, Decimal('0.00'))
        self.assertEqual(order.total, Decimal('27.00'))
        self.variant.sale_price = None
        self.variant.price = Decimal('50.00')
        self.variant.save()
        self.assertEqual(order.items.get().unit_price, Decimal('15.00'))

    def test_sale_change_requires_review_again(self):
        self.client.post(self.url('checkout'), self.data)
        self.variant.sale_price = Decimal('10.00')
        self.variant.save()
        response = self.client.post(self.url('checkout'), dict(self.data, action='submit'))
        self.assertContains(response, 'Your order changed')

    def test_sale_validation_and_database_constraint(self):
        for value in ('-1', '20', '21'):
            self.variant.sale_price = Decimal(value)
            with self.assertRaises(ValidationError):
                self.variant.full_clean()
            with self.assertRaises(IntegrityError), transaction.atomic():
                self.variant.save()
        self.variant.sale_price = Decimal('0')
        self.variant.full_clean()
        self.variant.save()
        self.assertEqual(self.variant.effective_price, Decimal('0'))

    def test_variant_editor_exposes_and_validates_sale(self):
        data = dict(name='Standard', sku='WURM', price='20', sale_price='25',
                    active='on', fulfillment_method='pod')
        form = VariantForm(data, instance=self.variant)
        self.assertIn('sale_price', form.errors)
        data['sale_price'] = '15'
        form = VariantForm(data, instance=self.variant)
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.sale_price, Decimal('15'))

    def test_sale_display_cart_and_sorting(self):
        self.variant.sale_price = Decimal('15.00')
        self.variant.save()
        ProductVariant.objects.create(product=self.variant.product, sku='OTHER', price='18')
        other = Product.objects.create(name='Other product', slug='other', published=True)
        ProductVariant.objects.create(product=other, sku='OTHER-PRODUCT', price='17')
        response = self.client.get(self.url('home') + '?sort=price_asc')
        self.assertEqual(response.context['products'][0].pk, self.variant.product_id)
        self.assertEqual(response.context['products'][0].starting_price, Decimal('15'))
        response = self.client.get(self.url('home') + '?sort=price_desc')
        self.assertEqual(response.context['products'][0].pk, other.pk)
        response = self.client.get(self.url('product', 'pin'))
        self.assertContains(response, '<del>$20.00</del>', html=True)
        response = self.client.get(self.url('cart'))
        self.assertEqual(response.context['cart_total'], Decimal('30'))
        self.assertContains(response, '$15.00')

    def test_threshold_boundaries_disabled_and_coupon_disabled(self):
        branding = StoreBranding.objects.create(free_shipping_threshold='50', coupon_code='')
        self.assertEqual(totals(Decimal('49.99'), 'standard', '')['shipping_cost'], Decimal('6.95'))
        self.assertEqual(totals(Decimal('50'), 'standard', '')['shipping_cost'], Decimal('0'))
        with self.assertRaises(ValueError):
            totals(Decimal('50'), 'standard', 'DISCOUNT')
        branding.free_shipping_threshold = None
        branding.save()
        self.assertEqual(totals(Decimal('500'), 'standard', '')['shipping_cost'], Decimal('6.95'))
