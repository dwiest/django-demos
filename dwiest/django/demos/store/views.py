import logging

from django.contrib.auth.decorators import permission_required
from django.db import transaction
from django.db.models import Max, Min, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .cart import KEY, cart_context
from .forms import AddToCartForm, CatalogForm, ProductForm, QuantityForm, VariantFormSet, PhotoUploadForm, PhotoDetailsForm
from .models import Catalog, Product, ProductPhoto
from .media import delete_image, upload_image


logger = logging.getLogger(__name__)
PREFIX = 'dwiest-django-demos/store/'


def page(request, template, **context):
    context.update(cart_context(request))
    return render(request, PREFIX + template, context)


def home(request, slug=None):
    catalogs = Catalog.objects.filter(published=True)
    catalog = get_object_or_404(catalogs, slug=slug) if slug else None
    products = Product.objects.filter(published=True).prefetch_related('photos').annotate(
        starting_price=Min('variants__price', filter=Q(variants__active=True)))
    if catalog:
        products = products.filter(catalogs=catalog)
    return page(request, 'home.html', catalogs=catalogs, catalog=catalog, products=products)


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
        if quantity <= 99:
            stored[key] = quantity
            request.session[KEY] = stored
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
                    ProductPhoto.objects.create(
                        product=item, bucket=bucket, key=key, sort_order=position + index,
                        width=prepared['width'], height=prepared['height'])
            return redirect('demos:store:product_edit', pk=item.pk)
        except Exception:
            logger.exception('Store photo upload failed for product %s', item.pk)
            for bucket, key in uploaded:
                delete_image(bucket, key)
            form.add_error(None, 'Photos could not be saved. Please try again or check the S3 configuration.')
    return page(request, 'photos.html', product=item, photo_upload=form)


@permission_required(('demo_store.change_product', 'demo_store.change_productphoto'), raise_exception=True)
@require_POST
def edit_photo(request, pk, photo_pk):
    photo = get_object_or_404(ProductPhoto, pk=photo_pk, product_id=pk)
    form = PhotoDetailsForm(request.POST, instance=photo)
    if form.is_valid():
        form.save()
        return redirect('demos:store:product_edit', pk=pk)
    return page(request, 'photo_edit.html', photo=photo, form=form)


@permission_required(('demo_store.change_product', 'demo_store.delete_productphoto'), raise_exception=True)
@require_POST
def delete_photo(request, pk, photo_pk):
    photo = get_object_or_404(ProductPhoto, pk=photo_pk, product_id=pk)
    photo.delete()
    return redirect('demos:store:product_edit', pk=pk)
