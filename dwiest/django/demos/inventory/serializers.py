from rest_framework import serializers
from .models import InventoryItem, InventoryList, InventoryEntry, InventoryTransaction


class StrictSerializer(serializers.ModelSerializer):
    def to_internal_value(self, data):
        if not isinstance(data, dict):
            raise serializers.ValidationError('Expected an object.')
        unknown = set(data) - {k for k, v in self.fields.items() if not v.read_only}
        if unknown:
            raise serializers.ValidationError({k: 'Unknown or read-only field.' for k in unknown})
        if 'quantity' in data and type(data['quantity']) is not int:
            raise serializers.ValidationError({'quantity': 'Expected an integer.'})
        return super().to_internal_value(data)


class ItemSerializer(StrictSerializer):
    class Meta:
        model = InventoryItem
        fields = ['id', 'name', 'description', 'status']
        read_only_fields = ['id']


class ListSerializer(ItemSerializer):
    class Meta(ItemSerializer.Meta):
        model = InventoryList


class EntrySerializer(StrictSerializer):
    class Meta:
        model = InventoryEntry
        fields = ['id', 'item', 'inventory_list', 'quantity', 'status', 'date_added']
        read_only_fields = ['id', 'date_added']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        owner = self.context['request'].user
        self.fields['item'].queryset = InventoryItem.objects.filter(owner=owner)
        self.fields['inventory_list'].queryset = InventoryList.objects.filter(owner=owner)

    def validate_quantity(self, value):
        from .services import validate_quantity
        validate_quantity(value)
        return value


class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = InventoryTransaction
        fields = ['id', 'entry', 'actor', 'operation', 'quantity', 'before', 'after',
                  'source', 'reference_id', 'metadata', 'idempotency_key', 'created_at']
        read_only_fields = fields
