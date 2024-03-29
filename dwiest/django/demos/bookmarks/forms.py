from datetime import date
from django import forms
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import connection, IntegrityError
from django.db.models import Q
from django.forms import widgets
from django.utils.translation import ugettext, ugettext_lazy as _
from enum import Enum, auto
from ..conf import settings
from .models import Bookmark, Tag, BookmarkTag
from datetime import date

class DateInput(forms.DateInput):
  input_type = 'date'

class QuickBookmarkForm(forms.Form):

  class Fields(str, Enum):
    DATE = 'date'
    OWNER = 'owner'
    URL = 'url'

  class Errors(str, Enum):
    DUPLICATE_URL = auto()

  error_messages = {
    Errors.DUPLICATE_URL:
      _(settings.DEMOS_BOOKMARKS_DUPLICATE_URL_ERROR),
    }

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
    self.fields[self.Fields.DATE].widget.attrs['max'] = date.today()

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
    try:
      self.bookmark.save()
    except IntegrityError as e:
      raise self.get_duplicate_url_error()

  @classmethod
  def get_duplicate_url_error(cls):
    return forms.ValidationError(
      cls.error_messages[cls.Errors.DUPLICATE_URL],
      code=cls.Errors.DUPLICATE_URL
      )


class BaseBookmarkForm(forms.ModelForm):

  class Fields(str, Enum):
    ARTICLE_DATE = 'article_date'
    DESCRIPTION = 'description'
    STATUS = 'status'
    TITLE = 'title'
    UNREAD = 'unread'
    URL = 'url'

  class DateInput(forms.DateInput):
    input_type = 'date'

  max_status = MaxValueValidator(1, "Status is more than the maximum allowed value.")
  min_status = MinValueValidator(-1, "Status is less than the minimum allowed value.")

  def clean_status(self):
    status = self.cleaned_data['status']
    self.max_status(status)
    self.min_status(status)
    return status


class BookmarkForm(BaseBookmarkForm):

  class Meta:
    model = Bookmark
    fields =  ['article_date', 'description', 'status', 'title', 'unread', 'url']
    widgets = {
      BaseBookmarkForm.Fields.ARTICLE_DATE: BaseBookmarkForm.DateInput(
        attrs = {
          'class': settings.DEMOS_BOOKMARKS_ARTICLE_DATE_CLASS,
          }
        ),
      BaseBookmarkForm.Fields.DESCRIPTION: forms.Textarea(
        attrs = {
          'class': settings.DEMOS_BOOKMARKS_DESCRIPTION_CLASS,
          }
        ),
      BaseBookmarkForm.Fields.STATUS: widgets.Select(
        attrs = {
          'class': settings.DEMOS_BOOKMARKS_STATUS_CLASS,
          },
        choices=[
          (-1, 'Deleted'),
          (0, 'Active'),
          (1, 'Hidden'),
          ],
        ),
      BaseBookmarkForm.Fields.TITLE: forms.TextInput(
        attrs = {
          'class': settings.DEMOS_BOOKMARKS_TITLE_CLASS,
          }
        ),
      BaseBookmarkForm.Fields.UNREAD: widgets.CheckboxInput(
        attrs = {
          'class': settings.DEMOS_BOOKMARKS_UNREAD_CLASS,
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
    self.fields['unread'].label = settings.DEMOS_BOOKMARKS_UNREAD_LABEL
    self.fields[BaseBookmarkForm.Fields.ARTICLE_DATE].max = date.today()

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
        'class': settings.DEMOS_BOOKMARKS_FILTER_CLASS,
        },
      ),
    )

  month = forms.IntegerField(
    label=None,
    initial=None,
    required=False,
    widget=widgets.Select(
      choices=[
        (0, '-'),
        (1, 'January'),
        (2, 'February'),
        (3, 'March'),
        (4, 'April'),
        (5, 'May'),
        (6, 'June'),
        (7, 'July'),
        (8, 'August'),
        (9, 'September'),
        (10, 'October'),
        (11, 'November'),
        (12, 'December'),
        ],
      ),
    )

  year = forms.IntegerField(
    label=None,
    initial=None,
    required=False,
    )

  show_deleted = forms.BooleanField(
    label="Show deleted",
    initial=False,
    required=False,
    )

  show_hidden = forms.BooleanField(
    label="Show hidden",
    initial=False,
    required=False,
    )

  hide_read = forms.BooleanField(
    label="Hide read",
    initial=False,
    required=False,
    )


  def __init__(self, filter=None, *args, **kwargs):
    super().__init__(*args, **kwargs)
    if filter:
      print("filter is {}".format(filter))

    with connection.cursor() as cursor:
      cursor.execute("select distinct strftime('%Y',article_date) as year from demos_bookmark where article_date is not null order by year desc;")
      rows = cursor.fetchall()
      years = []
      for row in rows:
        years.append((int(row[0]),row[0]))
      self.fields['year'].widget = widgets.Select(choices=years)

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


class BookmarkSearchForm(forms.Form):

  class Fields(str, Enum):
    FIELD = 'field'
    TERM = 'term'

  class Errors(str, Enum):
    pass

  error_messages = {}

  field_defaults = {
    Fields.TERM: None,
  }

  term = forms.CharField(
    label=None,
    initial=None,
    required=False,
    widget=forms.TextInput(
      attrs={
        'class': None,
        }
      ),
    )

  field = forms.CharField(
    label=None,
    initial='title',
    required=True,
    widget=widgets.RadioSelect(
      choices=[
        ('title', 'Title'),
        ('description', 'Description'),
        ('url', 'URL'),
        ('all', 'All Fields')
        ],
      attrs={
        'class': None,
        },
      ),
    )

  def getQ(self):
    field = self.cleaned_data['field']
    term = self.cleaned_data['term']

    if field == 'title':
      q = Q(title__contains=term)
    elif field == 'description':
      q = Q(description__contains=term)
    elif field == 'url':
      q = Q(url__contains=term)
    else: # all
      q = Q(title__contains=term) | Q(description__contains=term) | Q(url__contains=term)

    return q


class TagForm(forms.ModelForm):
  class Meta:
    model = Tag
    exclude = ["created_at", "last_modified"]

class BookmarkTagForm(forms.ModelForm):
  class Meta:
    model = BookmarkTag
    exclude = ["owner_id"]
