from decimal import Decimal

from .models import ProductVariant


KEY = 'demo_store_cart'


def cart_context(request):
    stored = request.session.get(KEY, {})
    quantities = {key: value for key, value in stored.items()
                  if key.isdigit() and isinstance(value, int) and 1 <= value <= 99}
    variants = ProductVariant.objects.filter(
        pk__in=quantities, active=True, product__published=True,
    ).select_related('product')
    rows = []
    valid = {}
    for variant in variants:
        quantity = quantities[str(variant.pk)]
        valid[str(variant.pk)] = quantity
        rows.append({'variant': variant, 'quantity': quantity,
                     'subtotal': variant.price * quantity})
    if valid != stored:
        request.session[KEY] = valid
    return {'cart_rows': rows, 'cart_count': sum(valid.values()),
            'cart_total': sum((row['subtotal'] for row in rows), Decimal('0.00'))}
