from datetime import date
from django import forms
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import connection, IntegrityError
from django.db.models import Q
from django.forms import widgets
from django.utils.translation import ugettext, ugettext_lazy as _
from enum import Enum, auto
from ..conf import settings
from .models import Journal, JournalEntry
from datetime import date

class DateInput(forms.DateInput):
  input_type = 'date'


class JournalForm(forms.ModelForm):
  class Meta:
    model = Journal 

    fields = ['id', 'name', 'description', 'status', 'owner']

  class Fields(str, Enum):
    NAME = 'name'
    OWNER = 'owner'
    DESCRIPTION = 'description'
    STATUS = 'status'

  class Errors(str, Enum):
    DUPLICATE_NAME = auto()

  error_messages = {
    Errors.DUPLICATE_NAME:
      _(settings.DEMOS_JOURNAL_DUPLICATE_NAME_ERROR),
    }

  field_defaults = {
    #Fields.URL: settings.DEMOS_BOOKMARKS_URL_DEFAULT
  }

  name = forms.CharField(
    label=settings.DEMOS_JOURNAL_NAME_LABEL,
    initial=settings.DEMOS_JOURNAL_NAME_DEFAULT,
    required=False,
    widget=forms.TextInput(
      attrs={
        'class': settings.DEMOS_JOURNAL_NAME_CLASS
        }
      ),
    )

#  def __init__(self, *args, **kwargs):
#    super().__init__(*args, **kwargs)
#    print("created JournalForm")

  def is_valid(self):
    print(self.is_bound)
    print(self.errors)
    print(str(self))
    return self.is_bound and not self.errors


class BaseJournalEntryForm(forms.ModelForm):

  class DateInput(forms.DateInput):
    input_type = 'date'

  class Fields(str, Enum):
    CONTENT = 'content'
    DATE = 'date'
    STATUS = 'status'


class JournalEntryForm(BaseJournalEntryForm):
  class Meta:
    model = JournalEntry 

    fields = ['date', 'content', 'status']

    widgets = {
      BaseJournalEntryForm.Fields.DATE: BaseJournalEntryForm.DateInput(
#        attrs = {
#          'class': settings.DEMOS_BOOKMARKS_ARTICLE_DATE_CLASS,
#          'max' : date.today(),
#          }
        ),
      BaseJournalEntryForm.Fields.CONTENT: forms.Textarea(
#        attrs = {
#          'class': settings.DEMOS_BOOKMARKS_DESCRIPTION_CLASS,
#          }
        ),
      BaseJournalEntryForm.Fields.STATUS: widgets.Select(
#        attrs = {
#          'class': settings.DEMOS_BOOKMARKS_STATUS_CLASS,
#          },
        choices=[
          (-1, 'Deleted'),
          (0, 'Active'),
          (1, 'Hidden'),
          ],
        ),
      }

  class Errors(str, Enum):
    DUPLICATE_DATE = auto()

  error_messages = {
    Errors.DUPLICATE_DATE:
      _(settings.DEMOS_JOURNAL_DUPLICATE_DATE_ERROR),
    }

  field_defaults = {
  }

  def is_valid(self):
    print(self.is_bound)
    print(self.errors)
    print(str(self))
    return self.is_bound and not self.errors
