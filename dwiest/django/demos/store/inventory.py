"""Stock changes and order allocations share the caller's database transaction."""
from functools import wraps
from django.db import transaction
from django.db.models import F
from .models import ProductVariant, StockMovement


class InventoryError(ValueError):
    pass


def check(variant, quantity):
    if not variant.purchasable or not variant.product.published:
        raise InventoryError('{}: {}.'.format(variant, variant.availability))
    if variant.fulfillment_method == 'stock' and quantity > variant.available_stock:
        raise InventoryError('{}: only {} available.'.format(variant, variant.available_stock))


@transaction.atomic
def movement(variant_id, on_hand=0, reserved=0, reason='', order=None, actor=None):
    # Conditional SQL update prevents overselling even where row locks are unavailable.
    updated = ProductVariant.objects.filter(pk=variant_id, stock_reserved__gte=-reserved).filter(
        stock_on_hand__gte=F('stock_reserved') + reserved - on_hand)
    if not updated.update(stock_on_hand=F('stock_on_hand') + on_hand,
                          stock_reserved=F('stock_reserved') + reserved):
        raise InventoryError('Stock changed or the adjustment would consume reserved stock. Reload and try again.')
    StockMovement.objects.create(variant_id=variant_id, on_hand_change=on_hand,
        reserved_change=reserved, reason=reason, order=order, actor=actor)


@transaction.atomic
def allocate(item, quantity, actor=None):
    variant = ProductVariant.objects.select_for_update().select_related('product').get(pk=item.variant_id)
    check(variant, quantity)
    local = min(quantity, variant.available_stock) if variant.fulfillment_method != 'pod' else 0
    if local:
        movement(variant.pk, reserved=local, reason='Order allocation', order=item.order, actor=actor)
    item.stock_quantity = local
    item.pod_quantity = quantity - local
    item.inventory_tracked = True
    item.delivery_estimate = variant.delivery_note(quantity)
    item.save(update_fields=['stock_quantity', 'pod_quantity', 'inventory_tracked', 'delivery_estimate'])


@transaction.atomic
def revise(order, forms, status, actor):
    if order.status in ('fulfilled', 'cancelled'):
        return
    for form in sorted(forms, key=lambda f: f.instance.variant_id or 0):
        item = form.instance
        old = order.items.get(pk=item.pk)
        if not old.inventory_tracked:
            continue  # Historical orders never reserved inventory.
        quantity = 0 if form.cleaned_data.get('DELETE') or status == 'cancelled' else form.cleaned_data['quantity']
        if quantity != old.quantity or not quantity:
            if old.stock_quantity:
                movement(old.variant_id, reserved=-old.stock_quantity, reason='Order allocation released', order=order, actor=actor)
            item.stock_quantity = item.pod_quantity = 0
            item.delivery_estimate = ''
            if quantity:
                if not item.variant_id:
                    raise InventoryError('The original variant is unavailable.')
                allocate(item, quantity, actor)
            else:
                item.save(update_fields=['stock_quantity', 'pod_quantity', 'delivery_estimate'])
        if status == 'fulfilled' and item.stock_quantity:
            movement(item.variant_id, on_hand=-item.stock_quantity, reserved=-item.stock_quantity,
                     reason='Order shipped', order=order, actor=actor)


def inventory_errors(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        try:
            return view(request, *args, **kwargs)
        except InventoryError as error:
            from .views import page
            return page(request, 'inventory_error.html', inventory_error=str(error))
    return wrapped
