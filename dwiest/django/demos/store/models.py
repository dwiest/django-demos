from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.utils.functional import cached_property


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

    @property
    def cover_photo(self):
        return next(iter(self.photos.all()), None)

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


class ProductPhoto(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='photos')
    bucket = models.CharField(max_length=255, editable=False)
    key = models.CharField(max_length=1024, unique=True, editable=False)
    alt_text = models.CharField(max_length=255, blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    width = models.PositiveIntegerField(editable=False)
    height = models.PositiveIntegerField(editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['sort_order', 'pk']

    def __str__(self):
        return '{} photo {}'.format(self.product, self.pk)

    @cached_property
    def url(self):
        from .media import photo_url
        return photo_url(self)
