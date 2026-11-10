"""Manual customer shipments; supplier deliveries to the shop are not shipments."""
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from .models import StoreOrder, Shipment, ShipmentLine, OrderEvent
from .inventory import movement
from .orders import notify


@transaction.atomic
def create_shipment(order_id, data, actor):
    order = StoreOrder.objects.select_for_update().get(pk=order_id)
    existing = Shipment.objects.filter(submission_key=data['submission_key']).first()
    if existing:
        if existing.order_id != order_id:
            raise ValueError('Invalid shipment submission.')
        return existing
    if order.status in ('fulfilled', 'cancelled'):
        raise ValueError('This order cannot be shipped.')
    if data['shipped_at'] > timezone.now():
        raise ValueError('Shipment date cannot be in the future.')
    allocations = []
    for item in order.items.select_for_update().all():
        previous = item.shipment_lines.aggregate(quantity=Sum('quantity'), stock=Sum('stock_quantity'))
        quantity = data.get('quantity_{}'.format(item.pk), 0)
        if quantity < 0 or quantity > item.quantity - (previous['quantity'] or 0):
            raise ValueError('Shipment quantity exceeds remaining quantity for {}.'.format(item.sku))
        if quantity:
            stock = min(quantity, item.stock_quantity - (previous['stock'] or 0)) if item.inventory_tracked else 0
            if data['fulfillment_method'] == 'supplier' and stock:
                raise ValueError('Items allocated from stock must be shipped by you. Ship stock items first.')
            allocations.append((item, quantity, stock))
    if not allocations:
        raise ValueError('Select at least one item to ship.')
    shipment = Shipment.objects.create(order=order, **{key: data[key] for key in
        ('carrier', 'tracking_number', 'tracking_url', 'shipped_at', 'fulfillment_method', 'supplier', 'private_notes', 'submission_key')})
    for item, quantity, stock in allocations:
        if stock:
            movement(item.variant_id, on_hand=-stock, reserved=-stock, reason='Shipment dispatched', order=order, actor=actor)
        ShipmentLine.objects.create(shipment=shipment, item=item, quantity=quantity, stock_quantity=stock)
    order.status = 'fulfilled' if order.fulfillment_status == 'Shipped' else 'processing'
    if order.status == 'fulfilled':
        order.fulfilled_at = shipment.shipped_at
    order.save()
    event = OrderEvent.objects.create(order=order, actor=actor, message='Shipment dispatched via {}. Tracking: {}.'.format(shipment.carrier, shipment.tracking_number))
    shipment.event = event
    shipment.save(update_fields=['event'])
    if data.get('notify_customer'):
        transaction.on_commit(lambda: notify(event.pk))
    return shipment
