from datetime import date
from django import forms
from django.forms import widgets
from enum import Enum
from ..conf import settings
from .models import Bookmark
from datetime import date

class DateInput(forms.DateInput):
  input_type = 'date'

class QuickBookmarkForm(forms.Form):

  class Fields(str, Enum):
    DATE = 'date'
    OWNER = 'owner'
    URL = 'url'

  class Errors(str, Enum):
    pass

  error_messages = {}

  field_defaults = {
    Fields.URL: settings.DEMOS_BOOKMARKS_URL_DEFAULT
  }

  date = forms.DateField(
    label=None,
    initial=None,
    required=False,
#    widget=forms.SelectDateWidget(
    widget=DateInput(
      attrs={
        'class': None,
        'max' : date.today(),
        }
      ),
    )

  url = forms.URLField(
    label=settings.DEMOS_BOOKMARKS_URL_LABEL,
    initial=settings.DEMOS_BOOKMARKS_URL_DEFAULT,
    required=False,
    widget=forms.URLInput(
      attrs={
        'class': settings.DEMOS_BOOKMARKS_URL_CLASS
        }
      ),
    )

  def __init__(self, owner=None, *args, **kwargs):
    super().__init__(*args, **kwargs)

    self.owner = owner
    url = self.fields[self.Fields.URL].initial

    if 'data' in kwargs: # bound form
      if self.Fields.URL not in kwargs['data']:
        new_data = kwargs['data'].copy()
        new_data[self.Fields.URL] = url
        self.data = new_data
      else:
        text = kwargs['data'][self.Fields.URL]

  def process(self):
    self.bookmark = Bookmark(
      owner=self.owner,
      url=self.cleaned_data[self.Fields.URL],
      article_date=self.cleaned_data[self.Fields.DATE],
      )

  def save(self):
    self.bookmark.save()


class BaseBookmarkForm(forms.ModelForm):

  class Fields(str, Enum):
    ARTICLE_DATE = 'article_date'
    DESCRIPTION = 'description'
    TITLE = 'title'
    URL = 'url'

  class DateInput(forms.DateInput):
    input_type = 'date'


class BookmarkForm(BaseBookmarkForm):

  class Meta:
    model = Bookmark
    fields =  ['article_date', 'description', 'title', 'url']
    widgets = {
      BaseBookmarkForm.Fields.ARTICLE_DATE: BaseBookmarkForm.DateInput(
        attrs = {
          'class': settings.DEMOS_BOOKMARKS_ARTICLE_DATE_CLASS,
          'max' : date.today(),
          }
        ),
      BaseBookmarkForm.Fields.DESCRIPTION: forms.Textarea(
        attrs = {
          'class': settings.DEMOS_BOOKMARKS_DESCRIPTION_CLASS,
          }
        ),
      BaseBookmarkForm.Fields.TITLE: forms.TextInput(
        attrs = {
          'class': settings.DEMOS_BOOKMARKS_TITLE_CLASS,
          }
        ),
      BaseBookmarkForm.Fields.URL: forms.TextInput(
        attrs = {
          'class': settings.DEMOS_BOOKMARKS_URL_CLASS,
          }
        ),
      }

  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.fields['title'].required = False


class BookmarkFilterForm(forms.Form):

  class Fields(str, Enum):
    FILTER = 'filter'
    MONTH = 'month'
    YEAR = 'year'

  class Errors(str, Enum):
    pass

  error_messages = {}

  field_defaults = {
    Fields.FILTER: None,
  }

  filter = forms.CharField(
    label=None,
    initial='Untitled',
    required=False,
#    widget=forms.RadioSelect(
    widget=widgets.RadioSelect(
      choices=[
        ('none', 'None'),
        ('undated', 'Undated'),
        ('untitled', 'Untitled'),
        ('date', 'date')
        ],
      attrs={
        'class': None,
        },
      ),
    )

  def __init__(self, filter=None, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.fields['filter'].initial = 'date'
    self.fields['filter'].value = 'date'
    if filter:
      print("filter is {}".format(filter))
    print("initial {}".format(self.fields['filter'].initial))
    print("value {}".format(self.fields['filter'].value))

   # url = self.fields[self.Fields.URL].initial

#    if 'data' in kwargs: # bound form
#      if self.Fields.URL not in kwargs['data']:
#        new_data = kwargs['data'].copy()
#        new_data[self.Fields.URL] = url
#        self.data = new_data
#      else:
#        text = kwargs['data'][self.Fields.URL]

  def process(self):
    pass
