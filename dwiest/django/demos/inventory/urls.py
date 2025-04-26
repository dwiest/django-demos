from django.urls import path
from .views import *
from django.views.generic import TemplateView

app_name = 'inventory'

urlpatterns = [
  path('',
    InventoryListHomeView.as_view(), name='home'),
  path('list_edit',
    InventoryListEditView.as_view(), name='list_edit'),
  path('list_view',
    InventoryListView.as_view(), name='list_view'),
  path('list_create',
    InventoryListEditView.as_view(), name='list_create'),
  path('item_create',
    InventoryItemEditView.as_view(), name='item_create'),
  path('item_edit',
    InventoryItemEditView.as_view(), name='item_edit'),
  path('item_view',
    InventoryItemView.as_view(), name='item_view'),
  path('entry_create',
    InventoryEntryEditView.as_view(), name='entry_create'),
  path('entry_edit',
    InventoryEntryEditView.as_view(), name='entry_edit'),
  #path('',
  #  TemplateView.as_view(
  #    template_name="dwiest-django-demos/inventory/home.html"), name='home')
]
