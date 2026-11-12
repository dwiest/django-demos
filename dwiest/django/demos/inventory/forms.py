from datetime import date
from django import forms
#from django.core.validators import MaxValueValidator, MinValueValidator
#from django.db import connection, IntegrityError
#from django.db.models import Q
from django.forms import widgets
from django.utils.translation import ugettext, ugettext_lazy as _
from enum import Enum, auto
#from ..conf import settings
from .models import InventoryList, InventoryItem, InventoryEntry
from datetime import date


class DateInput(forms.DateInput):
  input_type = 'date'


class InventoryListForm(forms.ModelForm):
  class Meta:
    model = InventoryList
    exclude = ['owner','created_at']
    widgets = {
      'status': widgets.NumberInput(
        attrs = {
          'max'  : 1,
          'min'  : -1,
          'class' : 'status'
          }
        ),
      }


  class Fields(str, Enum):
    NAME = 'name'
    OWNER = 'owner'
    STATUS = 'status'

  class Errors(str, Enum):
    DUPLICATE_NAME = auto()

  error_messages = {
    Errors.DUPLICATE_NAME:
#      _(settings.DEMOS_NEWS_ITEM_DUPLICATE_NAME_ERROR),
      'duplicate_name',
    }

  field_defaults = {
    #Fields.URL: settings.DEMOS_BOOKMARKS_URL_DEFAULT
  }

  name = forms.CharField(
#    label=settings.DEMOS_NEWS_ITEM_NAME_LABEL,
    label='Name',
#    initial=settings.DEMOS_NEWS_ITEM_NAME_DEFAULT,
    initial='Name',
    required=False,
    widget=forms.TextInput(
      attrs={
#        'class': settings.DEMOS_NEWS_ITEM_NAME_CLASS
        'class':'name_field' 
        }
      ),
    )

#  def __init__(self, *args, **kwargs):
#    super().__init__(*args, **kwargs)
#    print("created NewsItemForm")

  def is_valid(self):
    print(self.is_bound)
    print(self.errors)
    print(str(self))

    return self.is_bound and not self.errors


class InventoryItemForm(forms.ModelForm):
  class Meta:
    model = InventoryItem
    exclude = ['owner','created_at']
    widgets = {
      'status': widgets.NumberInput(
        attrs = {
          'max'  : 1,
          'min'  : -1,
          'class' : 'status'
          }
        ),
      }


  class Fields(str, Enum):
    NAME = 'name'
    OWNER = 'owner'
    LIST = 'list'
    STATUS = 'status'

  class Errors(str, Enum):
    DUPLICATE_NAME = auto()

  error_messages = {
    Errors.DUPLICATE_NAME:
#      _(settings.DEMOS_NEWS_ITEM_DUPLICATE_NAME_ERROR),
      'duplicate_name',
    }

  field_defaults = {
    #Fields.URL: settings.DEMOS_BOOKMARKS_URL_DEFAULT
  }

  name = forms.CharField(
#    label=settings.DEMOS_NEWS_ITEM_NAME_LABEL,
    label='Name',
#    initial=settings.DEMOS_NEWS_ITEM_NAME_DEFAULT,
    initial='Name',
    required=False,
    widget=forms.TextInput(
      attrs={
#        'class': settings.DEMOS_NEWS_ITEM_NAME_CLASS
        'class':'name_field' 
        }
      ),
    )

#  def __init__(self, *args, **kwargs):
#    super().__init__(*args, **kwargs)
#    print("created NewsItemForm")

  def is_valid(self):
    print(self.is_bound)
    print(self.errors)
    print(str(self))

    return self.is_bound and not self.errors


class InventoryEntryForm(forms.ModelForm):
  class Meta:
    model = InventoryEntry
    exclude = ['owner','created_at']
    widgets = {
      'status': widgets.NumberInput(
        attrs = {
          'max'  : 1,
          'min'  : -1,
          'class' : 'status'
          }
        ),
      }


  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    owner = self.instance.owner
    self.fields['item'].queryset = InventoryItem.objects.filter(owner=owner)
    self.fields['inventory_list'].queryset = InventoryList.objects.filter(owner=owner)
    self.fields['quantity'].min_value = 0
    self.fields['quantity'].widget.attrs['min'] = 0

  def clean_quantity(self):
    from .services import validate_quantity
    quantity = self.cleaned_data['quantity']
    validate_quantity(quantity)
    return quantity

  def save(self, commit=True):
    from django.db import transaction
    from .services import adjust_quantity, create_entry, owned_entries
    if not commit:
      raise ValueError('InventoryEntryForm requires commit=True for audited writes.')
    with transaction.atomic():
      if not self.instance.pk:
        self.instance = create_entry(owner=self.instance.owner,
          item_id=self.cleaned_data['item'].pk,
          inventory_list_id=self.cleaned_data['inventory_list'].pk,
          quantity=self.cleaned_data['quantity'], status=self.cleaned_data['status'])
      else:
        # Keep ledger meaning stable: an entry's item and list cannot be reassigned.
        current = owned_entries(self.instance.owner).get(pk=self.instance.pk)
        if (current.item_id, current.inventory_list_id) != (self.cleaned_data['item'].pk,
                                                          self.cleaned_data['inventory_list'].pk):
          raise forms.ValidationError('Create a new entry to change its item or list.')
        adjust_quantity(owner=self.instance.owner, entry_id=self.instance.pk,
                        operation='set', quantity=self.cleaned_data['quantity'])
        current.status = self.cleaned_data['status']
        current.save(update_fields=['status', 'last_modified'])
        current.refresh_from_db()
        self.instance = current
    return self.instance

  class Fields(str, Enum):
    NAME = 'name'
    OWNER = 'owner'
    ITEM = 'item'
    LIST = 'inventory_list'
    STATUS = 'status'
    QUANTITY = 'quantity'

  class Errors(str, Enum):
    DUPLICATE_NAME = auto()

  error_messages = {
    Errors.DUPLICATE_NAME:
#      _(settings.DEMOS_NEWS_ITEM_DUPLICATE_NAME_ERROR),
      'duplicate_name',
    }

  field_defaults = {
    #Fields.URL: settings.DEMOS_BOOKMARKS_URL_DEFAULT
  }

#  def __init__(self, *args, **kwargs):
#    super().__init__(*args, **kwargs)
#    print("created NewsItemForm")

  def is_valid(self):
    print(self.is_bound)
    print(self.errors)
    print(str(self))

    return self.is_bound and not self.errors
