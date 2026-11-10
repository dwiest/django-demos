"""Mock commerce services. Never store card details or treat simulation as payment."""
import logging
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone
from django.template.loader import render_to_string

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
        branding = StoreBranding.objects.filter(pk=1).first() or StoreBranding()
        context = {'order': event.order, 'event': event, 'branding': branding}
        template = 'dwiest-django-demos/store/email/order_notification'
        count = send_mail(
            '{} order {} update'.format(branding.name, event.order.number),
            render_to_string(template + '.txt', context),
            settings.DEFAULT_FROM_EMAIL, [event.order.email],
            html_message=render_to_string(template + '.html', context))
        if count != 1:
            raise RuntimeError('Email backend did not acknowledge delivery.')
        event.email_sent_at = timezone.now()
        event.email_error = ''
    except Exception:
        logger.exception('Order notification failed for event %s', event.pk)
        event.email_error = 'Email delivery failed. Check mail configuration and retry.'
    event.save(update_fields=['email_sent_at', 'email_error'])
