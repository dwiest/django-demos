import uuid
from decimal import Decimal

from django.conf import settings

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.utils.functional import cached_property
from django.utils import timezone


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
    def has_purchasable_variants(self):
        variants = getattr(self, 'available_variants', None)
        if variants is None:
            variants = self.variants.all()
        return any(variant.purchasable for variant in variants)

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
    sale_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                                    validators=[MinValueValidator(Decimal('0'))],
                                    help_text='Optional sale price below the regular price; blank ends the sale.')

    @property
    def effective_price(self):
        return self.sale_price if self.sale_price is not None else self.price

    def clean(self):
        super().clean()
        if self.sale_price is not None and self.price is not None and self.sale_price >= self.price:
            raise ValidationError({'sale_price': 'Sale price must be below the regular price.'})

    active = models.BooleanField(default=True)
    fulfillment_method = models.CharField(max_length=20, default='pod', choices=[
        ('pod', 'Print on demand'), ('stock', 'Stock only'),
        ('hybrid', 'Stock first, then print on demand')])
    coming_soon = models.BooleanField(default=False, help_text='Visible, but cannot be purchased.')
    stock_on_hand = models.PositiveIntegerField(default=0, editable=False)
    stock_reserved = models.PositiveIntegerField(default=0, editable=False)
    stock_estimate = models.CharField(max_length=180, blank=True, help_text='Dispatch estimate for stocked items.')
    production_estimate = models.CharField(max_length=180, blank=True, help_text='Production and dispatch estimate for print-on-demand items.')

    @property
    def available_stock(self):
        return self.stock_on_hand - self.stock_reserved

    @property
    def purchasable(self):
        return self.active and not self.coming_soon and (self.fulfillment_method != 'stock' or self.available_stock > 0)

    @property
    def availability(self):
        if self.coming_soon:
            return 'Coming soon'
        if not self.active:
            return 'Unavailable'
        if self.fulfillment_method != 'pod' and self.available_stock > 0:
            return 'In stock'
        return 'Sold out' if self.fulfillment_method == 'stock' else 'Print on demand'

    def delivery_note(self, quantity=1):
        if not self.purchasable:
            return self.availability
        local = min(quantity, self.available_stock) if self.fulfillment_method != 'pod' else 0
        notes = []
        if local:
            notes.append('{} from stock{}'.format(local, ': ' + self.stock_estimate if self.stock_estimate else ''))
        if quantity > local:
            notes.append('{} print on demand{}'.format(quantity - local, ': ' + self.production_estimate if self.production_estimate else ''))
        return '; '.join(notes)


    class Meta:
        ordering = ['pk']
        constraints = [models.CheckConstraint(check=models.Q(price__gte=0),
                                              name='demo_store_price_nonnegative'),
                       models.CheckConstraint(check=models.Q(sale_price__isnull=True) | (
                           models.Q(sale_price__gte=0) & models.Q(sale_price__lt=models.F('price'))),
                           name='store_sale_below_regular'),
                       models.CheckConstraint(check=models.Q(stock_on_hand__gte=models.F('stock_reserved')), name='store_reservations_within_stock')]

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
    show_item_status = models.BooleanField(default=True, help_text='Show availability badges and option status labels on catalog and product pages.')
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
    shipping_policy = models.TextField(blank=True, help_text="Plain text. Blank uses the generic starting policy; review before taking live orders.")
    returns_policy = models.TextField(blank=True, help_text="Plain text. Blank uses the generic starting policy; review before taking live orders.")
    privacy_policy = models.TextField(blank=True, help_text="Plain text. Blank uses the generic starting policy; review before taking live orders.")
    terms_policy = models.TextField(blank=True, help_text="Plain text. Blank uses the generic starting policy; review before taking live orders.")
    contact_policy = models.TextField(blank=True, help_text="Plain text. Blank uses the generic starting policy; review before taking live orders.")

    footer_link_label = models.CharField(max_length=80, blank=True)
    footer_link_url = models.URLField(blank=True)
    shipping_rate = models.DecimalField(max_digits=10, decimal_places=2, default='6.95', validators=[MinValueValidator(0)])
    free_shipping_threshold = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)], help_text='After discounts; blank disables free shipping.')
    shipping_estimate = models.CharField(max_length=180, blank=True, default='Processing time varies by item.')
    coupon_code = models.CharField(max_length=40, blank=True, default='DISCOUNT')
    coupon_percent = models.DecimalField(max_digits=5, decimal_places=2, default=5, validators=[MinValueValidator(0), MaxValueValidator(100)])
    thank_you_heading = models.CharField(max_length=180, default='Thank you for your order!',
        help_text='Heading on the order confirmation page.')
    thank_you_message = models.TextField(blank=True, default='Your order has been received.',
        help_text='Optional message below the heading. Plain text only; leave blank to hide.')
    thank_you_button_label = models.CharField(max_length=80, default='Continue shopping',
        help_text='Label for the link back to the storefront.')
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
    def fulfillment_status(self):
        shipped = sum(line.quantity for shipment in self.shipments.all() for line in shipment.lines.all())
        total = sum(item.quantity for item in self.items.all())
        return 'Shipped' if shipped and shipped == total else ('Partially shipped' if shipped else 'Unfulfilled')

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

    stock_quantity = models.PositiveIntegerField(default=0, editable=False)
    pod_quantity = models.PositiveIntegerField(default=0, editable=False)
    inventory_tracked = models.BooleanField(default=False, editable=False)
    delivery_estimate = models.CharField(max_length=500, blank=True, editable=False)

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


class CustomerAddress(models.Model):
    """Address book entries, independent of immutable order shipping snapshots."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    name = models.CharField(max_length=160)
    line1 = models.CharField(max_length=200)
    line2 = models.CharField(max_length=200, blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=2)
    postal_code = models.CharField(max_length=10)
    country = models.CharField(max_length=2, default='US', editable=False)

    class Meta:
        ordering = ['pk']


class StockMovement(models.Model):
    variant = models.ForeignKey(ProductVariant, on_delete=models.PROTECT, related_name='stock_movements')
    order = models.ForeignKey(StoreOrder, null=True, blank=True, on_delete=models.SET_NULL)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    on_hand_change = models.IntegerField(default=0)
    reserved_change = models.IntegerField(default=0)
    reason = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-pk']


class Shipment(models.Model):
    order = models.ForeignKey(StoreOrder, related_name='shipments', on_delete=models.PROTECT)
    carrier = models.CharField(max_length=80)
    tracking_number = models.CharField(max_length=100)
    tracking_url = models.URLField(blank=True)
    shipped_at = models.DateTimeField(default=timezone.now)
    fulfillment_method = models.CharField(max_length=20, choices=[('self', 'Shipped by me'), ('supplier', 'Shipped by supplier')], default='self')
    supplier = models.CharField(max_length=160, blank=True)
    private_notes = models.TextField(blank=True)
    event = models.OneToOneField(OrderEvent, null=True, blank=True, on_delete=models.PROTECT, related_name='shipment')
    submission_key = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    class Meta:
        ordering = ['shipped_at', 'pk']


class ShipmentLine(models.Model):
    shipment = models.ForeignKey(Shipment, related_name='lines', on_delete=models.CASCADE)
    item = models.ForeignKey(StoreOrderItem, related_name='shipment_lines', on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    stock_quantity = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['shipment', 'item'], name='store_shipment_item_unique'),
                       models.CheckConstraint(check=models.Q(quantity__gt=0), name='store_shipment_quantity_positive')]
