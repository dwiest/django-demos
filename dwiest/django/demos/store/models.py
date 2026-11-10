import uuid
from decimal import Decimal

from django.conf import settings

from django.core.validators import MinValueValidator, MaxValueValidator
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

    @property
    def featured_photos(self):
        photos = list(self.photos.all())
        featured = [photo for photo in photos if photo.sort_order == 0]
        return featured or photos[:1]

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
    version = models.PositiveIntegerField(default=1, editable=False)
    variant = models.ForeignKey(ProductVariant, null=True, blank=True, on_delete=models.SET_NULL,
                                related_name='photos', help_text='Optional purchase option represented by this photo.')
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


class ProductPhotoVersion(models.Model):
    """Retained immutable object locations, including after a photo/product is removed."""
    photo = models.ForeignKey(ProductPhoto, null=True, on_delete=models.SET_NULL, related_name='versions')
    version = models.PositiveIntegerField()
    bucket = models.CharField(max_length=255)
    key = models.CharField(max_length=1024)
    width = models.PositiveIntegerField()
    height = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-version']
        constraints = [models.UniqueConstraint(fields=['photo', 'version'], name='store_photo_version_unique')]

    @cached_property
    def url(self):
        from .media import photo_url
        return photo_url(self)


class StoreBranding(models.Model):
    """One storefront configuration; image bytes remain in S3."""
    name = models.CharField(max_length=100, default='Oddment Supply')
    tagline = models.CharField(max_length=180, default='Good finds. A little unexpected.')
    introduction = models.TextField(blank=True, default='Explore the collection and find your next favorite.')
    header_image_bucket = models.CharField(max_length=255, blank=True, editable=False)
    header_image_key = models.CharField(max_length=1024, blank=True, editable=False)
    header_image_alt = models.CharField(max_length=255, blank=True)
    footer_heading = models.CharField(max_length=120, default='Made for the everyday.')
    footer_text = models.TextField(blank=True, default='Small discoveries. Lasting favorites.')
    footer_image_bucket = models.CharField(max_length=255, blank=True, editable=False)
    footer_image_key = models.CharField(max_length=1024, blank=True, editable=False)
    footer_image_alt = models.CharField(max_length=255, blank=True)
    contact_email = models.EmailField(blank=True)
    footer_link_label = models.CharField(max_length=80, blank=True)
    footer_link_url = models.URLField(blank=True)
    coupon_code = models.CharField(max_length=40, blank=True, default='DISCOUNT')
    coupon_percent = models.DecimalField(max_digits=5, decimal_places=2, default=5, validators=[MinValueValidator(0), MaxValueValidator(100)])
    thank_you_image_bucket = models.CharField(max_length=255, blank=True, editable=False)
    thank_you_image_key = models.CharField(max_length=1024, blank=True, editable=False)
    thank_you_image_alt = models.CharField(max_length=255, blank=True)
    email_header = models.TextField(blank=True, help_text='Header text for order emails. Blank uses the store name. Plain text only.')
    email_footer = models.TextField(blank=True, help_text='Footer text for order emails, such as contact details. Plain text only.')
    email_header_image_bucket = models.CharField(max_length=255, blank=True, editable=False)
    email_header_image_key = models.CharField(max_length=1024, blank=True, editable=False)
    email_header_image_alt = models.CharField(max_length=255, blank=True)
    email_footer_image_bucket = models.CharField(max_length=255, blank=True, editable=False)
    email_footer_image_key = models.CharField(max_length=1024, blank=True, editable=False)
    email_footer_image_alt = models.CharField(max_length=255, blank=True)
    email_footer_heading = models.CharField(max_length=180, blank=True)
    email_shop_url = models.URLField(blank=True, help_text='Permanent HTTPS storefront link for emails.')
    email_help_url = models.URLField(blank=True, help_text='Optional HTTPS order help page.')
    copyright_text = models.CharField(max_length=180, blank=True)

    class Meta:
        verbose_name_plural = 'Store branding'
        constraints = [models.CheckConstraint(check=models.Q(pk=1), name='demo_store_single_branding')]

    def save(self, *args, **kwargs):
        self.pk = 1
        return super().save(*args, **kwargs)

    def image_url(self, location):
        from types import SimpleNamespace
        from .media import photo_url
        key = getattr(self, location + '_image_key')
        if not key:
            return ''
        return photo_url(SimpleNamespace(bucket=getattr(self, location + '_image_bucket'), key=key))

    @cached_property
    def header_image_url(self):
        return self.image_url('header')

    @cached_property
    def footer_image_url(self):
        return self.image_url('footer')


    @cached_property
    def thank_you_image_url(self):
        return self.image_url('thank_you')

    @cached_property
    def email_header_image_url(self):
        from .media import permanent_url
        return permanent_url(self.email_header_image_bucket, self.email_header_image_key)

    @cached_property
    def email_footer_image_url(self):
        from .media import permanent_url
        return permanent_url(self.email_footer_image_bucket, self.email_footer_image_key)



class ShippingAddress(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    name = models.CharField(max_length=160)
    line1 = models.CharField(max_length=200)
    line2 = models.CharField(max_length=200, blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=2)
    postal_code = models.CharField(max_length=10)
    country = models.CharField(max_length=2, default='US', editable=False)

    def __str__(self):
        return '{}, {}, {} {} {}'.format(self.name, self.line1, self.city, self.state, self.postal_code)


class StoreOrder(models.Model):
    STATUS = [('placed', 'Placed'), ('processing', 'Processing'), ('fulfilled', 'Fulfilled'), ('cancelled', 'Cancelled')]
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    checkout_key = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    email = models.EmailField()
    shipping_address = models.OneToOneField(ShippingAddress, on_delete=models.PROTECT)
    status = models.CharField(max_length=20, choices=STATUS, default='placed')
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    coupon_code = models.CharField(max_length=40, blank=True)
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    shipping_method = models.CharField(max_length=40)
    shipping_cost = models.DecimalField(max_digits=10, decimal_places=2)
    tax = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2)
    payment_method = models.CharField(max_length=30)
    payment_acknowledgment = models.CharField(max_length=120)
    tracking_number = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    fulfilled_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    @property
    def shipping_label(self):
        from .forms import SHIPPING
        return SHIPPING.get(self.shipping_method, (self.shipping_method, ''))[0]

    @property
    def number(self):
        return 'RW-{:08d}'.format(self.pk)

    def __str__(self):
        return self.number


class StoreOrderItem(models.Model):
    order = models.ForeignKey(StoreOrder, related_name='items', on_delete=models.CASCADE)
    variant = models.ForeignKey(ProductVariant, null=True, on_delete=models.SET_NULL)
    product_name = models.CharField(max_length=160)
    variant_name = models.CharField(max_length=160)
    sku = models.CharField(max_length=80)
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(99)])
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    image_bucket = models.CharField(max_length=255, blank=True)
    image_key = models.CharField(max_length=1024, blank=True)
    image_alt = models.CharField(max_length=255, blank=True)

    @property
    def email_image_url(self):
        from .media import permanent_url
        return permanent_url(self.image_bucket, self.image_key)


    @property
    def subtotal(self):
        return self.quantity * self.unit_price


class OrderEvent(models.Model):
    order = models.ForeignKey(StoreOrder, related_name='events', on_delete=models.CASCADE)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    email_sent_at = models.DateTimeField(null=True, blank=True)
    email_error = models.TextField(blank=True)

    class Meta:
        ordering = ['created_at', 'pk']
