from django import forms
from enum import Enum
from ..conf import settings
from .models import Bookmark

class QuickBookmarkForm(forms.Form):

  class Fields(str, Enum):
    URL = 'url'

  class Errors(str, Enum):
    pass

  error_messages = {}

  field_defaults = {
    Fields.URL: settings.DEMOS_BOOKMARKS_URL_DEFAULT
  }

  url = forms.CharField(
    label=settings.DEMOS_BOOKMARKS_URL_LABEL,
    initial=settings.DEMOS_BOOKMARKS_URL_DEFAULT,
    required=False,
    widget=forms.TextInput(
      attrs={
        'class': settings.DEMOS_BOOKMARKS_URL_CLASS
        }
      ),
    )

  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)

    url = self.fields[self.Fields.URL].initial

    if 'data' in kwargs: # bound form
      if self.Fields.URL not in kwargs['data']:
        new_data = kwargs['data'].copy()
        new_data[self.Fields.URL] = url
        self.data = new_data
      else:
        text = kwargs['data'][self.Fields.URL]

  def process(self):
    self.bookmark = Bookmark(url=self.cleaned_data[self.Fields.URL])

  def save(self):
    self.bookmark.save()


class BaseBookmarkForm(forms.ModelForm):

  class Fields(str, Enum):
    ARTICLE_DATE = 'article_date'
    DESCRIPTION = 'description'
    TITLE = 'title'
    URL = 'url'

class BookmarkForm(BaseBookmarkForm):

  class Meta:
    model = Bookmark
    fields =  ['article_date', 'description', 'title', 'url']
    widgets = {
      BaseBookmarkForm.Fields.ARTICLE_DATE: forms.TextInput(
        attrs = {
          'class': settings.DEMOS_BOOKMARKS_ARTICLE_DATE_CLASS,
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
