"""Mock commerce services. Never store card details or treat simulation as payment."""
import logging
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from .models import OrderEvent, StoreBranding
from .forms import SHIPPING

logger = logging.getLogger(__name__)


def totals(subtotal, shipping_method, coupon):
    branding = StoreBranding.objects.filter(pk=1).first() or StoreBranding()
    code = coupon.strip().upper()
    if code and (not branding.coupon_code or code != branding.coupon_code.strip().upper()):
        raise ValueError('That coupon is not active.')
    percent = branding.coupon_percent if code else Decimal('0')
    discount = (subtotal * percent / 100).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
    shipping = Decimal(SHIPPING[shipping_method][1])
    return dict(subtotal=subtotal, coupon_code=code, discount_percent=percent,
                discount=discount, shipping_cost=shipping, tax=Decimal('0.00'),
                total=subtotal - discount + shipping)


def notify(event_id):
    event = OrderEvent.objects.select_related('order').get(pk=event_id)
    if event.email_sent_at:
        return
    try:
        count = send_mail('RottenWorld order {} update'.format(event.order.number),
                         '{}\n\nOrder: {}\nStatus: {}\nTotal: ${} USD\nPayment: simulated; no funds charged.\nUSPS tracking: {}\n'.format(
                             event.message + '\n\nItems:\n' + '\n'.join('{} × {} ({}) — ${} USD'.format(item.quantity, item.product_name, item.variant_name, item.subtotal) for item in event.order.items.all()) + '\nShip to: ' + str(event.order.shipping_address) + ' ' + event.order.shipping_address.line2, event.order.number, event.order.get_status_display(),
                             event.order.total, event.order.tracking_number or 'Not shipped'),
                         settings.DEFAULT_FROM_EMAIL, [event.order.email])
        if count != 1:
            raise RuntimeError('Email backend did not acknowledge delivery.')
        event.email_sent_at = timezone.now()
        event.email_error = ''
    except Exception:
        logger.exception('Order notification failed for event %s', event.pk)
        event.email_error = 'Email delivery failed. Check mail configuration and retry.'
    event.save(update_fields=['email_sent_at', 'email_error'])
