import logging
import hashlib
import json
import uuid
from urllib.parse import urlsplit, urlunsplit
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.core.cache import cache
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods
from .forms import GuestOrderLookupForm
from .guest_orders import make_token, read_order
from django.core.paginator import Paginator
from django.http import Http404, HttpResponse
from django.utils import timezone

from django.contrib.auth.decorators import permission_required
from django.db import transaction
from django.db.models import Max, Min, Q, Prefetch
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .cart import KEY, cart_context
from .forms import AddToCartForm, CatalogForm, ProductForm, QuantityForm, VariantFormSet, PhotoUploadForm, PhotoDetailsForm, StoreBrandingForm, CheckoutForm, OrderUpdateForm, OrderItemFormSet, ShippingAddressForm, OrderEmailForm
from .models import Catalog, Product, ProductPhoto, StoreBranding, StoreOrder, StoreOrderItem, OrderEvent, ProductVariant
from .media import delete_image, upload_image, upload_asset, record_photo_version, snapshot_image
from .orders import totals, notify
from .inventory import check, allocate, revise, movement, InventoryError, inventory_errors


logger = logging.getLogger(__name__)
PREFIX = 'dwiest-django-demos/store/'


def page(request, template, **context):
    context['store_branding'] = StoreBranding.objects.filter(pk=1).first() or StoreBranding()
    context.update(cart_context(request))
    return render(request, PREFIX + template, context)


def home(request, slug=None):
    catalogs = Catalog.objects.filter(published=True)
    catalog = get_object_or_404(catalogs, slug=slug) if slug else None
    products = Product.objects.filter(published=True).prefetch_related(
        'photos', Prefetch('variants', queryset=ProductVariant.objects.filter(active=True),
                           to_attr='available_variants')).annotate(
        starting_price=Min('variants__price', filter=Q(variants__active=True)))
    if catalog:
        products = products.filter(catalogs=catalog)
    return page(request, 'home.html', catalogs=catalogs, catalog=catalog, products=products,
                cart_notice=request.session.pop('store_cart_notice', ''))


def product(request, slug):
    item = get_object_or_404(Product.objects.prefetch_related('photos'), published=True, slug=slug)
    return page(request, 'product.html', product=item, form=AddToCartForm(product=item))


def cart(request):
    return page(request, 'cart.html')


@require_POST
def add(request, slug):
    item = get_object_or_404(Product.objects.prefetch_related('photos'), published=True, slug=slug)
    form = AddToCartForm(request.POST, product=item)
    if form.is_valid():
        cart_context(request)
        stored = request.session.get(KEY, {}).copy()
        key = str(form.cleaned_data['variant'].pk)
        quantity = stored.get(key, 0) + form.cleaned_data['quantity']
        try:
            check(form.cleaned_data['variant'], quantity)
        except InventoryError as error:
            form.add_error('quantity', str(error))
            return page(request, 'product.html', product=item, form=form)
        if quantity <= 99:
            stored[key] = quantity
            request.session[KEY] = stored
            if request.POST.get('quick_add') == '1':
                request.session['store_cart_notice'] = '{} added to your cart.'.format(item.name)
                catalog_slug = request.POST.get('catalog', '')
                if catalog_slug and Catalog.objects.filter(slug=catalog_slug, published=True).exists():
                    return redirect('demos:store:catalog', slug=catalog_slug)
                return redirect('demos:store:home')
            return redirect('demos:store:cart')
        form.add_error('quantity', 'You can add up to 99 of each item.')
    return page(request, 'product.html', product=item, form=form)


@require_POST
def update(request, pk):
    cart_context(request)
    stored = request.session.get(KEY, {}).copy()
    key = str(pk)
    if key not in stored:
        return redirect('demos:store:cart')
    if request.POST.get('action') == 'remove':
        del stored[key]
    else:
        form = QuantityForm(request.POST)
        if not form.is_valid():
            return page(request, 'cart.html', cart_error='Enter a whole quantity from 1 to 99.')
        try:
            check(ProductVariant.objects.select_related('product').get(pk=pk), form.cleaned_data['quantity'])
        except InventoryError as error:
            return page(request, 'cart.html', cart_error=str(error))
        stored[key] = form.cleaned_data['quantity']
    request.session[KEY] = stored
    return redirect('demos:store:cart')


@permission_required(('demo_store.view_product', 'demo_store.view_catalog'), raise_exception=True)
def manage(request):
    return page(request, 'manage.html', products=Product.objects.all(), catalogs=Catalog.objects.all())


def edit_product(request, pk=None):
    item = get_object_or_404(Product, pk=pk) if pk else Product()
    form = ProductForm(request.POST if request.method == 'POST' else None, instance=item)
    variants = VariantFormSet(request.POST if request.method == 'POST' else None, instance=item)
    if request.method == 'POST' and form.is_valid() and variants.is_valid():
        with transaction.atomic():
            form.save()
            variants.save()
        return redirect('demos:store:manage')
    return page(request, 'edit.html', form=form, variants=variants, kind='product', photo_upload=PhotoUploadForm())


def edit_catalog(request, pk=None):
    item = get_object_or_404(Catalog, pk=pk) if pk else Catalog()
    form = CatalogForm(request.POST if request.method == 'POST' else None, instance=item)
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('demos:store:manage')
    return page(request, 'edit.html', form=form, kind='catalog')


product_create = permission_required(
    ('demo_store.add_product', 'demo_store.add_productvariant'), raise_exception=True)(edit_product)
product_edit = permission_required(
    ('demo_store.change_product', 'demo_store.add_productvariant',
     'demo_store.change_productvariant', 'demo_store.delete_productvariant'),
    raise_exception=True)(edit_product)
catalog_create = permission_required('demo_store.add_catalog', raise_exception=True)(edit_catalog)
catalog_edit = permission_required('demo_store.change_catalog', raise_exception=True)(edit_catalog)


@permission_required(('demo_store.change_product', 'demo_store.add_productphoto'), raise_exception=True)
@require_POST
def upload_photos(request, pk):
    item = get_object_or_404(Product, pk=pk)
    form = PhotoUploadForm(request.POST, request.FILES)
    uploaded = []
    if form.is_valid():
        try:
            with transaction.atomic():
                # Serialize uploads for this product on databases supporting row locks.
                Product.objects.select_for_update().get(pk=item.pk)
                last = item.photos.aggregate(last=Max('sort_order'))['last']
                position = 0 if last is None else last + 1
                for index, prepared in enumerate(form.cleaned_data['photos']):
                    bucket, key = upload_image(item, prepared)
                    uploaded.append((bucket, key))
                    photo = ProductPhoto.objects.create(
                        product=item, bucket=bucket, key=key, sort_order=position + index,
                        width=prepared['width'], height=prepared['height'])
                    record_photo_version(photo)
            return redirect('demos:store:product_edit', pk=item.pk)
        except Exception:
            logger.exception('Store photo upload failed for product %s', item.pk)
            for bucket, key in uploaded:
                delete_image(bucket, key)
            form.add_error(None, 'Photos could not be saved. Please try again or check the S3 configuration.')
    return page(request, 'photos.html', product=item, photo_upload=form)


@permission_required(('demo_store.change_product', 'demo_store.change_productphoto'), raise_exception=True)
def edit_photo(request, pk, photo_pk):
    photo = get_object_or_404(ProductPhoto, pk=photo_pk, product_id=pk)
    form = PhotoDetailsForm(request.POST if request.method == 'POST' else None,
                            request.FILES if request.method == 'POST' else None, instance=photo)
    uploaded = None
    if request.method == 'POST' and form.is_valid():
        try:
            with transaction.atomic():
                current = ProductPhoto.objects.select_for_update().get(pk=photo.pk)
                record_photo_version(current)
                prepared = form.cleaned_data.get('replacement_image')
                if prepared:
                    uploaded = upload_image(current.product, prepared)
                    current.bucket, current.key = uploaded
                    current.width, current.height = prepared['width'], prepared['height']
                    current.version += 1
                for field in ('alt_text', 'sort_order', 'variant'):
                    setattr(current, field, form.cleaned_data[field])
                current.save()
                record_photo_version(current)
            return redirect('demos:store:product_edit', pk=pk)
        except Exception:
            logger.exception('Photo replacement failed')
            if uploaded:
                delete_image(*uploaded)
            form.add_error(None, 'Photo could not be saved. Previous versions were retained.')
    return page(request, 'photo_edit.html', photo=photo, form=form)


@permission_required(('demo_store.change_product', 'demo_store.change_productphoto'), raise_exception=True)
@require_POST
def restore_photo(request, pk, photo_pk, version):
    from .models import ProductPhotoVersion
    with transaction.atomic():
        photo = get_object_or_404(ProductPhoto.objects.select_for_update(), pk=photo_pk, product_id=pk)
        previous = get_object_or_404(ProductPhotoVersion, photo=photo, version=version)
        record_photo_version(photo)
        for field in ('bucket', 'key', 'width', 'height'):
            setattr(photo, field, getattr(previous, field))
        photo.version += 1
        photo.save()
        record_photo_version(photo)
    return redirect('demos:store:photo_edit', pk=pk, photo_pk=photo_pk)


@permission_required(('demo_store.change_product', 'demo_store.delete_productphoto'), raise_exception=True)
@require_POST
def delete_photo(request, pk, photo_pk):
    photo = get_object_or_404(ProductPhoto, pk=photo_pk, product_id=pk)
    photo.delete()
    return redirect('demos:store:product_edit', pk=pk)


@permission_required('demo_store.change_storebranding', raise_exception=True)
def branding(request):
    instance = StoreBranding.objects.filter(pk=1).first() or StoreBranding()
    form = StoreBrandingForm(request.POST if request.method == 'POST' else None,
                             request.FILES if request.method == 'POST' else None, instance=instance)
    uploaded = []
    if request.method == 'POST' and form.is_valid():
        try:
            with transaction.atomic():
                previous = StoreBranding.objects.select_for_update().filter(pk=1).first()
                item = form.save(commit=False)
                for location in ('header', 'footer', 'email_header', 'email_footer', 'thank_you'):
                    bucket_field, key_field = location + '_image_bucket', location + '_image_key'
                    old_bucket = getattr(previous, bucket_field, '')
                    old_key = getattr(previous, key_field, '')
                    prepared = form.cleaned_data.get(location + '_image')
                    remove = form.cleaned_data.get('remove_' + location + '_image')
                    if prepared:
                        bucket, key = upload_asset('branding', prepared)
                        uploaded.append((bucket, key))
                    elif remove:
                        bucket, key = '', ''
                    else:
                        bucket, key = old_bucket, old_key
                    setattr(item, bucket_field, bucket)
                    setattr(item, key_field, key)
                item.save()
            return redirect('demos:store:home')
        except Exception:
            logger.exception('Store branding update failed')
            for bucket, key in uploaded:
                delete_image(bucket, key)
            form.add_error(None, 'Store settings could not be saved. Please try again or check the S3 configuration.')
    return page(request, 'branding.html', form=form,
                email_media_ready=bool(getattr(settings, 'STORE_MEDIA_PUBLIC_BASE_URL', '')))


@inventory_errors
def checkout(request):
    key = request.session.get('store_checkout_key')
    if not key:
        key = str(uuid.uuid4())
        request.session['store_checkout_key'] = key
    if request.method == 'POST':
        existing = StoreOrder.objects.filter(checkout_key=key).first()
        if existing:
            return redirect('demos:store:order_complete', token=existing.token)
    cart_data = cart_context(request)
    if request.method == 'GET' and cart_data['cart_rows'] and StoreOrder.objects.filter(checkout_key=key).exists():
        key = str(uuid.uuid4())
        request.session['store_checkout_key'] = key
    if not cart_data['cart_rows']:
        return redirect('demos:store:cart')
    initial = {'checkout_key': key, 'shipping_method': 'ground', 'payment_method': 'card_usd'}
    saved_addresses = []
    if request.user.is_authenticated:
        from .models import CustomerAddress
        saved_addresses = CustomerAddress.objects.filter(user=request.user)
        initial.update(email=request.user.email, name=request.user.get_full_name())
        if request.method == 'GET' and request.GET.get('address'):
            address = get_object_or_404(saved_addresses, pk=request.GET['address'])
            initial.update({field: getattr(address, field) for field in
                            ('name', 'line1', 'line2', 'city', 'state', 'postal_code')})
    form = CheckoutForm(request.POST if request.method == 'POST' else None, initial=initial)
    quote = None
    if request.method == 'POST' and form.is_valid():
        if str(form.cleaned_data['checkout_key']) != key:
            form.add_error(None, 'Checkout expired. Reload the checkout page.')
        else:
            try:
                quote = totals(cart_data['cart_total'], form.cleaned_data['shipping_method'], form.cleaned_data['coupon'])
            except ValueError as error:
                form.add_error('coupon', str(error))
        if not form.errors:
            review = hashlib.sha256(json.dumps({
                'fields': {k: str(v) for k, v in form.cleaned_data.items()},
                'quote': {k: str(v) for k, v in quote.items()},
                'items': [(row['variant'].pk, row['quantity'], str(row['variant'].price), row['delivery_note'], row['variant'].fulfillment_method, row['variant'].coming_soon) for row in cart_data['cart_rows']],
            }, sort_keys=True).encode()).hexdigest()
            if request.POST.get('action') == 'review':
                request.session['store_checkout_review'] = review
            elif request.session.get('store_checkout_review') != review:
                form.add_error(None, 'Your order changed. Update the order review before submitting.')
        if not form.errors and request.POST.get('action') == 'submit':
            with transaction.atomic():
                for row in cart_data['cart_rows']:
                    check(ProductVariant.objects.select_for_update().select_related('product').get(pk=row['variant'].pk), row['quantity'])
                address = form.save(commit=False)
                if request.user.is_authenticated:
                    address.user = request.user
                address.save()
                order, created = StoreOrder.objects.get_or_create(checkout_key=key, defaults=dict(
                    email=form.cleaned_data['email'], shipping_address=address,
                    user=request.user if request.user.is_authenticated else None,
                    shipping_method=form.cleaned_data['shipping_method'],
                    payment_method=form.cleaned_data['payment_method'],
                    payment_acknowledgment='SIMULATED-{}'.format(uuid.uuid4()), **quote))
                if created:
                    for row in cart_data['cart_rows']:
                        variant = row['variant']
                        order_item = StoreOrderItem.objects.create(order=order, variant=variant,
                            product_name=variant.product.name, variant_name=variant.name, sku=variant.sku,
                            quantity=row['quantity'], unit_price=variant.price, **snapshot_image(variant))
                        allocate(order_item, row['quantity'], request.user if request.user.is_authenticated else None)
                    event = OrderEvent.objects.create(order=order, message='Thank you! Your demo order has been received. No payment was collected.')
                    transaction.on_commit(lambda: notify(event.pk))
                else:
                    address.delete()
            receipts = request.session.get('store_receipts', [])
            request.session['store_receipts'] = (receipts + [str(order.token)])[-50:]
            request.session[KEY] = {}
            return redirect('demos:store:order_complete', token=order.token)
    return page(request, 'checkout.html', form=form, quote=quote, saved_addresses=saved_addresses)


def order_complete(request, token):
    # Session ownership avoids exposing customer addresses through shared links.
    if str(token) not in request.session.get('store_receipts', []):
        raise Http404
    order = get_object_or_404(StoreOrder, token=token)
    return page(request, 'order_complete.html', order=order)


@permission_required('demo_store.view_storeorder', raise_exception=True)
def order_list(request):
    orders = StoreOrder.objects.select_related('shipping_address')
    status = request.GET.get('status', '')
    query = request.GET.get('q', '').strip()
    if status in dict(StoreOrder.STATUS):
        orders = orders.filter(status=status)
    if query:
        orders = orders.filter(Q(email__icontains=query) | Q(shipping_address__name__icontains=query) |
                               Q(tracking_number__icontains=query))
    return page(request, 'orders.html', orders=Paginator(orders, 30).get_page(request.GET.get('page')), statuses=StoreOrder.STATUS)


@permission_required(('demo_store.view_storeorder', 'demo_store.change_storeorder'), raise_exception=True)
@inventory_errors
def order_edit(request, pk):
    with transaction.atomic():
        order = get_object_or_404(StoreOrder.objects.select_for_update(), pk=pk)
        form = OrderUpdateForm(request.POST if request.method == 'POST' else None,
                               initial={'status': order.status, 'tracking_number': order.tracking_number})
        address_form = ShippingAddressForm(request.POST if request.method == 'POST' else None, instance=order.shipping_address, prefix='address')
        items = OrderItemFormSet(request.POST if request.method == 'POST' else None, queryset=order.items.all())
        if request.method == 'POST' and form.is_valid() and items.is_valid() and address_form.is_valid():
            data = form.cleaned_data
            remaining = [f for f in items.forms if f.cleaned_data and not f.cleaned_data.get('DELETE')]
            changed_items = items.has_changed()
            if any(f.cleaned_data.get('id') and f.cleaned_data['id'].order_id != order.pk for f in items.forms):
                return HttpResponse('Invalid order item.', status=400)
            changed = data['status'] != order.status or data['tracking_number'] != order.tracking_number or changed_items or address_form.has_changed()
            if order.status in ('fulfilled', 'cancelled') and changed:
                form.add_error(None, 'Completed or cancelled orders are read-only. You can still send messages.')
            elif not remaining:
                form.add_error(None, 'Keep at least one order item, or cancel the order.')
            elif not changed and not data['message'].strip():
                form.add_error('message', 'Enter a message or make a change.')
            else:
                revise(order, items.forms, data['status'], request.user)
                details = []
                if address_form.has_changed():
                    details.append('Shipping address updated: {}.'.format(address_form.instance))
                    address_form.save()
                if changed_items:
                    before = ', '.join('{} × {}'.format(item.quantity, item.sku) for item in order.items.all())
                    items.save()
                    order.subtotal = sum((item.subtotal for item in order.items.all()), Decimal('0.00'))
                    order.discount = (order.subtotal * order.discount_percent / 100).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
                    order.total = order.subtotal - order.discount + order.shipping_cost + order.tax
                    details.append('Items changed from {} to {}. New total: ${} USD. Payment remains simulated.'.format(before, ', '.join('{} × {}'.format(item.quantity, item.sku) for item in order.items.all()), order.total))
                if data['status'] != order.status:
                    details.append('Status changed from {} to {}.'.format(order.status, data['status']))
                if data['tracking_number'] != order.tracking_number:
                    details.append('USPS tracking: {}.'.format(data['tracking_number']))
                order.status = data['status']
                order.tracking_number = data['tracking_number']
                if order.status == 'fulfilled' and not order.fulfilled_at:
                    order.fulfilled_at = timezone.now()
                if order.status == 'cancelled' and not order.cancelled_at:
                    order.cancelled_at = timezone.now()
                order.save()
                event = OrderEvent.objects.create(order=order, actor=request.user,
                    message='\n'.join(details + ([data['message']] if data['message'].strip() else [])))
                transaction.on_commit(lambda: notify(event.pk))
                return redirect('demos:store:order_edit', pk=pk)
    return page(request, 'order_edit.html', order=order, form=form, items=items, address_form=address_form,
                email_form=OrderEmailForm(initial={'email': order.email}))


@permission_required('demo_store.change_storeorder', raise_exception=True)
@require_POST
def retry_notification(request, pk, event_pk):
    event = get_object_or_404(OrderEvent, pk=event_pk, order_id=pk)
    notify(event.pk)
    return redirect('demos:store:order_edit', pk=pk)


@permission_required(('demo_store.view_storeorder', 'demo_store.change_storeorder'), raise_exception=True)
@require_POST
def order_email(request, pk):
    with transaction.atomic():
        order = get_object_or_404(StoreOrder.objects.select_for_update(), pk=pk)
        form = OrderEmailForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            if email == order.email:
                form.add_error('email', 'Enter a different email address.')
            else:
                previous = order.email
                order.email = email
                order.save(update_fields=['email', 'updated_at'])
                event = OrderEvent.objects.create(order=order, actor=request.user,
                    message='Order email corrected from {} to {}.'.format(previous, email))
                transaction.on_commit(lambda: notify(event.pk))
                return redirect('demos:store:order_edit', pk=pk)
    return page(request, 'order_edit.html', order=order, email_form=form,
                form=OrderUpdateForm(initial={'status': order.status, 'tracking_number': order.tracking_number}),
                address_form=ShippingAddressForm(instance=order.shipping_address, prefix='address'),
                items=OrderItemFormSet(queryset=order.items.all()))


@never_cache
@require_http_methods(['GET', 'POST'])
def guest_order_lookup(request):
    form = GuestOrderLookupForm(request.POST if request.method == 'POST' else None)
    submitted = False
    if request.method == 'POST' and form.is_valid():
        submitted = True
        # Limit mail by both recipient and source, including unsuccessful lookups.
        email = form.cleaned_data['email'].casefold()
        identity = hashlib.sha256(email.encode()).hexdigest()
        source = hashlib.sha256(request.META.get('REMOTE_ADDR', '').encode()).hexdigest()
        allowed = True
        for key, limit in [('email:' + identity, 3), ('ip:' + source, 10)]:
            key = 'store:guest-lookup:' + key
            cache.add(key, 0, timeout=3600)
            try:
                if cache.incr(key) > limit:
                    allowed = False
            except ValueError:
                allowed = False
        if allowed:
            number = int(form.cleaned_data['order_number'][3:])
            order = StoreOrder.objects.filter(pk=number, email__iexact=email).first() if number <= 9223372036854775807 else None
            if order:
                token = make_token(order)
                branding = StoreBranding.objects.filter(pk=1).first() or StoreBranding()
                path = reverse('demos:store:guest_order_detail', args=[token])
                origin = urlsplit(branding.email_shop_url)
                link = (urlunsplit(('https', origin.netloc, path, '', ''))
                        if origin.scheme == 'https' and origin.netloc else request.build_absolute_uri(path))
                context = {'order': order, 'branding': branding, 'lookup_url': link,
                           'email_title': 'View your order'}
                try:
                    send_mail('{}: view order {}'.format(branding.name, order.number),
                              render_to_string(PREFIX + 'email/guest_lookup.txt', context),
                              settings.DEFAULT_FROM_EMAIL, [order.email],
                              html_message=render_to_string(PREFIX + 'email/guest_lookup.html', context))
                except Exception:
                    logger.error('Guest order lookup email delivery failed')
    response = page(request, 'guest_lookup.html', form=form, submitted=submitted)
    # Preserve the same-origin Referer for HTTPS CSRF validation on form POSTs.
    response['Referrer-Policy'] = 'same-origin'
    return response


@never_cache
@require_http_methods(['GET'])
def guest_order_detail(request, token):
    order = read_order(token)
    response = page(request, 'guest_order.html', order=order)
    if order is None:
        response.status_code = 404
    response['Referrer-Policy'] = 'no-referrer'
    response['X-Robots-Tag'] = 'noindex, nofollow'
    return response


@permission_required('demo_store.change_productvariant', raise_exception=True)
def inventory(request):
    from .forms import StockAdjustmentForm
    from .models import StockMovement
    form = StockAdjustmentForm(request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and form.is_valid():
        try:
            movement(form.cleaned_data['variant'].pk, on_hand=form.cleaned_data['quantity'],
                     reason=form.cleaned_data['reason'], actor=request.user)
            return redirect('demos:store:inventory')
        except InventoryError as error:
            form.add_error(None, str(error))
    return page(request, 'inventory.html', form=form,
                variants=ProductVariant.objects.select_related('product').all(),
                movements=Paginator(StockMovement.objects.select_related('variant__product', 'actor', 'order'), 40).get_page(request.GET.get('page')))
