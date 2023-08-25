from datetime import date
from django import forms
#from django.core.validators import MaxValueValidator, MinValueValidator
#from django.db import connection, IntegrityError
#from django.db.models import Q
from django.forms import widgets
from django.utils.translation import ugettext, ugettext_lazy as _
from enum import Enum, auto
#from ..conf import settings
from .models import BillTo, Invoice, LineItem
from datetime import date


class DateInput(forms.DateInput):
  input_type = 'date'


class BillToForm(forms.ModelForm):
  class Meta:
    model = BillTo
    exclude = ['owner']

#    fields = ['id', 'name', 'status', 'owner']

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

  def __init__(self, *args, **kwargs):
    print("created {}".format(self.__class__.__name__))
    super().__init__(*args, **kwargs)

  def is_valid(self):
    print("BillToForm.is_valid()")
    print(self.is_bound)
    print(self.errors)
#    print(str(self))
    return self.is_bound and not self.errors


class InvoiceForm(forms.ModelForm):
  class Meta:
    model = Invoice
    exclude = ['owner']
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

  invoice_date = forms.DateField(
    label='Invoice Date:',
    initial=date.today(),
    required=False,
    widget=DateInput(
      attrs={
        'class': None,
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


class LineItemForm(forms.ModelForm):
  class Meta:
    model = LineItem
    exclude = ['owner']
    widgets = {
      'status': widgets.NumberInput(
        attrs = {
          'max'  : 1,
          'min'  : -1,
          'class' : 'inv_li_status'
          }
        ),
      'description': widgets.Textarea(
        attrs = {
          'rows' : 2,
          'cols' : 70,
          'class' : 'inv_li_description'
          }
        ),
#      'date': DateInput(
#        attrs = {
#          'max' : date.today(),
#          'class' : 'inv_li_date'
#          }
#        ),
      'rate': widgets.NumberInput(
        attrs = {
            'class' : 'inv_li_rate'
          }
        ),
      'quantity': widgets.NumberInput(
        attrs = {
            'class' : 'inv_li_quantity',
            'max'   : 24,
            'min'   : 0.25,
            'step'  : 0.25,

          }
        ),
      }

  class Fields(str, Enum):
    DATE = 'date'
    DESCRIPTION = 'description'
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

  date = forms.DateField(
    label=None,
    initial=None,
    required=False,
#    widget=forms.SelectDateWidget(
    widget=DateInput(
      attrs={
#        'max' : date.today(),
        'class' : 'inv_li_date'
        }
      ),
    )

