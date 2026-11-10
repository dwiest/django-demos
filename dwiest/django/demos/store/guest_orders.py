"""Expiring, order-specific guest access; changing the email revokes old links."""
from django.core import signing
from django.utils.crypto import constant_time_compare

SALT = 'demo-store.guest-order.v1'
MAX_AGE = 24 * 60 * 60


def make_token(order):
    return signing.dumps({'order': str(order.token), 'email': order.email}, salt=SALT)


def read_order(token):
    from .models import StoreOrder
    try:
        data = signing.loads(token, salt=SALT, max_age=MAX_AGE)
        order = StoreOrder.objects.select_related('shipping_address').get(token=data['order'])
        if constant_time_compare(data['email'], order.email):
            return order
    except (signing.BadSignature, StoreOrder.DoesNotExist, KeyError, TypeError, ValueError):
        pass
    return None
