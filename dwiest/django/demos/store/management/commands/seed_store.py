from decimal import Decimal

from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand
from django.db import transaction

from ...models import Catalog, Product, ProductVariant


class Command(BaseCommand):
    help = 'Create sample RottenWorld products and the Shop administrators group, without overwriting edits.'

    @transaction.atomic
    def handle(self, *args, **options):
        group, _ = Group.objects.get_or_create(name='Shop administrators')
        group.permissions.add(*Permission.objects.filter(content_type__app_label='demo_store'))
        for slug, name, description, product_name, product_slug, price, variants in [
            ('accessories', 'Accessories', 'Everyday RottenWorld essentials.',
             'RottenWorld hat', 'rottenworld-hat', '25.00', ['Black', 'Charcoal']),
            ('collectibles', 'Collectibles', 'Small pieces with plenty of personality.',
             'RottenWorld enamel pin', 'rottenworld-enamel-pin', '10.00', ['Standard']),
            ('posters', 'Posters', 'Make some room on your wall.',
             'RottenWorld poster', 'rottenworld-poster', '20.00', ['12 × 18 inches', '18 × 24 inches']),
        ]:
            catalog, _ = Catalog.objects.get_or_create(slug=slug, defaults={
                'name': name, 'description': description, 'published': True})
            product, created = Product.objects.get_or_create(slug=product_slug, defaults={
                'name': product_name, 'description': 'Sample RottenWorld merchandise. Details and artwork coming soon.',
                'published': True})
            if created:
                product.catalogs.add(catalog)
                for index, variant_name in enumerate(variants, 1):
                    ProductVariant.objects.create(product=product, name=variant_name,
                                                  sku='{}-{}'.format(product_slug.upper(), index),
                                                  price=Decimal(price))
        self.stdout.write(self.style.SUCCESS('Sample store ready. Assign shop managers to Shop administrators.'))
