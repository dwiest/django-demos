from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models


class Catalog(models.Model):
    name = models.CharField(max_length=160)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    published = models.BooleanField(default=False)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Product(models.Model):
    name = models.CharField(max_length=160)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    image_url = models.URLField(blank=True, help_text='Optional HTTPS product image URL.')
    image_alt = models.CharField(max_length=255, blank=True)
    published = models.BooleanField(default=False)
    catalogs = models.ManyToManyField(Catalog, related_name='products', blank=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class ProductVariant(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variants')
    name = models.CharField(max_length=160, default='Standard')
    sku = models.CharField(max_length=80, unique=True)
    price = models.DecimalField(max_digits=10, decimal_places=2,
                                validators=[MinValueValidator(Decimal('0'))])
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ['pk']
        constraints = [models.CheckConstraint(check=models.Q(price__gte=0),
                                              name='demo_store_price_nonnegative')]

    def __str__(self):
        return '{} — {}'.format(self.product, self.name)
