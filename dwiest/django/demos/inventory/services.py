"""Shared inventory writes. Callers must supply the authenticated owner."""
from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django.db.models import F
from django.shortcuts import get_object_or_404
from .models import InventoryEntry, InventoryItem, InventoryList, InventoryTransaction

MAX_QUANTITY = 2147483647


def validate_quantity(quantity):
    if type(quantity) is not int or not 0 <= quantity <= MAX_QUANTITY:
        raise ValidationError({'quantity': 'Use a non-negative integer up to 2147483647.'})


def owned_entries(owner):
    return InventoryEntry.objects.filter(owner=owner, item__owner=owner, inventory_list__owner=owner)


def require_owner(owner):
    if owner is None or not owner.is_authenticated:
        raise ValidationError('An authenticated owner is required.')


@transaction.atomic
def adjust_quantity(*, owner, entry_id, operation, quantity, source='manual',
                    reference_id='', metadata=None, idempotency_key=None):
    require_owner(owner)
    validate_quantity(quantity)
    if operation not in ('add', 'remove', 'set'):
        raise ValidationError({'operation': 'Use add, remove, or set.'})
    metadata = {} if metadata is None else metadata
    if not isinstance(metadata, dict):
        raise ValidationError({'metadata': 'Expected an object.'})
    for field, value, limit in [('source', source, 32), ('reference_id', reference_id, 128),
                                ('idempotency_key', idempotency_key, 128)]:
        if field == 'idempotency_key' and value is None:
            continue
        if not isinstance(value, str) or len(value) > limit or (field != 'reference_id' and not value):
            raise ValidationError({field: 'Invalid string or length.'})
    # Serialize keys across entries for a user on row-locking databases.
    if connection.features.has_select_for_update:
        type(owner).objects.select_for_update().get(pk=owner.pk)
    # A real write serializes SQLite writers too (select_for_update alone does not).
    # On PostgreSQL this takes the same row lock before reading the balance.
    qs = owned_entries(owner).filter(pk=entry_id)
    if not qs.update(quantity=F('quantity')):
        get_object_or_404(qs)
    entry = qs.get()
    if idempotency_key:
        previous = InventoryTransaction.objects.filter(actor=owner, idempotency_key=idempotency_key).first()
        if previous:
            signature = (entry_id, operation, quantity, source, reference_id, metadata)
            if signature != (previous.entry_id, previous.operation, previous.quantity,
                             previous.source, previous.reference_id, previous.metadata):
                raise ValidationError({'idempotency_key': 'Already used for a different request.'})
            return previous
    before = entry.quantity
    after = quantity if operation == 'set' else before + (quantity if operation == 'add' else -quantity)
    validate_quantity(after)
    entry.quantity = after
    entry.save(update_fields=['quantity', 'last_modified'])
    return InventoryTransaction.objects.create(entry=entry, actor=owner, operation=operation,
        quantity=quantity, before=before, after=after, source=source, reference_id=reference_id,
        metadata=metadata, idempotency_key=idempotency_key)


@transaction.atomic
def create_entry(*, owner, item_id, inventory_list_id, quantity=1, status=0, source='manual'):
    require_owner(owner)
    validate_quantity(quantity)
    item = get_object_or_404(InventoryItem, owner=owner, pk=item_id)
    inventory_list = get_object_or_404(InventoryList, owner=owner, pk=inventory_list_id)
    entry = InventoryEntry.objects.create(owner=owner, item=item, inventory_list=inventory_list,
                                          quantity=0, status=status)
    adjust_quantity(owner=owner, entry_id=entry.pk, operation='set', quantity=quantity, source=source)
    entry.refresh_from_db()
    return entry
