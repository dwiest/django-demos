from datetime import date
from django import forms
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import connection, IntegrityError
from django.db.models import Q
from django.forms import widgets
from django.utils.translation import ugettext, ugettext_lazy as _
from enum import Enum, auto
#from ..conf import settings
from .models import NewsItem
from datetime import date

class DateInput(forms.DateInput):
  input_type = 'date'


class NewsItemForm(forms.ModelForm):
  class Meta:
    model = NewsItem 

    fields = ['id', 'name', 'description', 'status', 'owner', 'begin_time', 'end_time']

  class Fields(str, Enum):
    NAME = 'name'
    OWNER = 'owner'
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


#class BaseNewsItemEntryForm(forms.ModelForm):
#
#  class DateInput(forms.DateInput):
#    input_type = 'date'
#
#  class Fields(str, Enum):
#    CONTENT = 'content'
#    DATE = 'date'
#    STATUS = 'status'
#
#
#class NewsItemEntryForm(BaseNewsItemEntryForm):
#  class Meta:
#    model = NewsItemEntry 
#
#    fields = ['date', 'content', 'status']
#
#    widgets = {
#      BaseNewsItemEntryForm.Fields.DATE: BaseNewsItemEntryForm.DateInput(
##        attrs = {
##          'class': settings.DEMOS_BOOKMARKS_ARTICLE_DATE_CLASS,
##          'max' : date.today(),
##          }
#        ),
#      BaseNewsItemEntryForm.Fields.CONTENT: forms.Textarea(
##        attrs = {
##          'class': settings.DEMOS_BOOKMARKS_DESCRIPTION_CLASS,
##          }
#        ),
#      BaseNewsItemEntryForm.Fields.STATUS: widgets.Select(
##        attrs = {
##          'class': settings.DEMOS_BOOKMARKS_STATUS_CLASS,
##          },
#        choices=[
#          (-1, 'Deleted'),
#          (0, 'Active'),
#          (1, 'Hidden'),
#          ],
#        ),
#      }
#
#  class Errors(str, Enum):
#    DUPLICATE_DATE = auto()
#
#  error_messages = {
#    Errors.DUPLICATE_DATE:
#      _(settings.DEMOS_NEWS_ITEM_DUPLICATE_DATE_ERROR),
#    }
#
#  field_defaults = {
#  }
#
#  def is_valid(self):
#    print(self.is_bound)
#    print(self.errors)
#    print(str(self))
#    return self.is_bound and not self.errors
