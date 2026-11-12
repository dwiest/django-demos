from django.urls import path
from . import api_views as api

urlpatterns = [
    path('items/', api.ItemListAPI.as_view(), name='api_items'),
    path('items/<int:pk>/', api.ItemDetailAPI.as_view(), name='api_item'),
    path('lists/', api.ListListAPI.as_view(), name='api_lists'),
    path('lists/<int:pk>/', api.ListDetailAPI.as_view(), name='api_list'),
    path('entries/', api.EntryListAPI.as_view(), name='api_entries'),
    path('entries/<int:pk>/', api.EntryDetailAPI.as_view(), name='api_entry'),
    path('entries/<int:pk>/adjust/', api.AdjustmentAPI.as_view(), name='api_adjust'),
    path('entries/<int:pk>/transactions/', api.TransactionListAPI.as_view(), name='api_entry_transactions'),
    path('transactions/', api.TransactionListAPI.as_view(), name='api_transactions'),
]
