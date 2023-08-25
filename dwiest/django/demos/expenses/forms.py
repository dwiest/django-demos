from datetime import date
from django import forms
#from django.core.validators import MaxValueValidator, MinValueValidator
#from django.db import connection, IntegrityError
#from django.db.models import Q
from django.forms import widgets
from django.utils.translation import ugettext, ugettext_lazy as _
from enum import Enum, auto
#from ..conf import settings
from .models import *
from datetime import date


class DateInput(forms.DateInput):
  input_type = 'date'


class ExpenseListForm(forms.ModelForm):
  class Meta:
    model = ExpenseList
    exclude = ["owner"]

  def __init__(self, *args, **kwargs):
    print("created {}".format(self.__class__.__name__))
    super().__init__(*args, **kwargs)

  def is_valid(self):
    print("{}.is_valid()".format(self.__class__.__name__))
    print(self.is_bound)
    print(self.errors)
#    print(str(self))
    return self.is_bound and not self.errors

class ExpenseCategoryForm(forms.ModelForm):
  class Meta:
    model = ExpenseCategory
    exclude = ["owner"]

  def __init__(self, *args, **kwargs):
    print("created {}".format(self.__class__.__name__))
    super().__init__(*args, **kwargs)

  def is_valid(self):
    print("{}.is_valid()".format(self.__class__.__name__))
    print(self.is_bound)
    print(self.errors)
#    print(str(self))
    return self.is_bound and not self.errors


class ExpenseForm(forms.ModelForm):
  class Meta:
    model = Expense
    exclude = []
    widgets = []

#    fields = ['id', 'name', 'status', 'owner']

  class Fields(str, Enum):
    NAME = 'name'
    OWNER = 'owner'

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

  def __init__(self, *args, **kwargs):
    print("created {}".format(self.__class__.__name__))
    super().__init__(*args, **kwargs)

  def is_valid(self):
    print("{}.is_valid()".format(self.__class__.__name__))
    print(self.is_bound)
    print(self.errors)
#    print(str(self))
    return self.is_bound and not self.errors
