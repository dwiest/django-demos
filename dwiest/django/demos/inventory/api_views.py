"""Owner-scoped DRF API. Quantity writes always go through services."""
from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from rest_framework import generics
from rest_framework.authentication import SessionAuthentication, BasicAuthentication
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import InventoryItem, InventoryList, InventoryTransaction
from .serializers import ItemSerializer, ListSerializer, EntrySerializer, TransactionSerializer
from .services import adjust_quantity, create_entry, owned_entries


class Pagination(PageNumberPagination):
    page_size = 40
    page_size_query_param = 'page_size'
    max_page_size = 100


class OwnerAPI:
    authentication_classes = [SessionAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated]
    pagination_class = Pagination

    def handle_exception(self, exc):
        if isinstance(exc, DjangoValidationError):
            exc = ValidationError(getattr(exc, 'message_dict', None) or exc.messages)
        return super().handle_exception(exc)

    def get_queryset(self):
        qs = self.model.objects.filter(owner=self.request.user).order_by('id')
        term = self.request.query_params.get('term', '').strip()
        return qs.filter(name__icontains=term) if term else qs

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class ItemListAPI(OwnerAPI, generics.ListCreateAPIView):
    model = InventoryItem
    serializer_class = ItemSerializer


class ItemDetailAPI(OwnerAPI, generics.RetrieveUpdateAPIView):
    model = InventoryItem
    serializer_class = ItemSerializer


class ListListAPI(OwnerAPI, generics.ListCreateAPIView):
    model = InventoryList
    serializer_class = ListSerializer


class ListDetailAPI(OwnerAPI, generics.RetrieveUpdateAPIView):
    model = InventoryList
    serializer_class = ListSerializer


class EntryListAPI(OwnerAPI, generics.ListCreateAPIView):
    serializer_class = EntrySerializer

    def get_queryset(self):
        qs = owned_entries(self.request.user).order_by('id')
        for field in ('inventory_list', 'item'):
            value = self.request.query_params.get(field)
            if value is not None:
                if not value.isdigit():
                    raise ValidationError({field: 'Expected an integer ID.'})
                qs = qs.filter(**{field + '_id': int(value)})
        term = self.request.query_params.get('term', '').strip()
        return qs.filter(item__name__icontains=term) if term else qs

    def perform_create(self, serializer):
        data = serializer.validated_data
        serializer.instance = create_entry(owner=self.request.user, item_id=data['item'].pk,
            inventory_list_id=data['inventory_list'].pk, quantity=data.get('quantity', 1),
            status=data.get('status', 0), source='api')


class EntryDetailAPI(OwnerAPI, generics.RetrieveAPIView):
    serializer_class = EntrySerializer

    def get_queryset(self):
        return owned_entries(self.request.user)


class AdjustmentAPI(OwnerAPI, APIView):
    def post(self, request, pk):
        if not isinstance(request.data, dict):
            raise ValidationError('Expected an object.')
        allowed = {'operation', 'quantity', 'source', 'reference_id', 'metadata', 'idempotency_key'}
        unknown = set(request.data) - allowed
        if unknown:
            raise ValidationError({key: 'Unknown field.' for key in unknown})
        if not request.data.get('idempotency_key'):
            raise ValidationError({'idempotency_key': 'Required for safe retries.'})
        event = adjust_quantity(owner=request.user, entry_id=pk,
            operation=request.data.get('operation'), quantity=request.data.get('quantity'),
            source=request.data.get('source', 'api'), reference_id=request.data.get('reference_id', ''),
            metadata=request.data.get('metadata', {}), idempotency_key=request.data['idempotency_key'])
        return Response(TransactionSerializer(event).data)


class TransactionListAPI(OwnerAPI, generics.ListAPIView):
    serializer_class = TransactionSerializer

    def get_queryset(self):
        qs = InventoryTransaction.objects.filter(actor=self.request.user).order_by('-id')
        if 'pk' in self.kwargs:
            entry = get_object_or_404(owned_entries(self.request.user), pk=self.kwargs['pk'])
            qs = qs.filter(entry=entry)
        return qs
