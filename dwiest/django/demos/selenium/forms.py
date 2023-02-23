from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from enum import Enum, auto
from selenium import webdriver
from ..conf import settings
import base64
from io import BytesIO


class SeleniumForm(forms.Form):
  class Fields(str, Enum):
    HEIGHT = 'height',
    URL = 'url',
    WIDTH = 'width',

  class Errors(str, Enum):
    SELENIUM_DRIVER = auto()
    URL_INVALID = auto()
    URL_MISSING_SCHEME = auto()

  error_messages = {
    Errors.SELENIUM_DRIVER: _(settings.DEMOS_SELENIUM_DRIVER_ERROR_MESSAGE),
    Errors.URL_INVALID: _(settings.DEMOS_SELENIUM_URL_INVALID_ERROR_MESSAGE),
    Errors.URL_MISSING_SCHEME: _(settings.DEMOS_SELENIUM_URL_MISSING_SCHEME_ERROR_MESSAGE),
  }

  url = forms.URLField(
    label=settings.DEMOS_SELENIUM_URL_FIELD_LABEL,
    initial=settings.DEMOS_SELENIUM_INITIAL_URL,
    widget=forms.TextInput(
      attrs={
        'class': settings.DEMOS_SELENIUM_URL_CLASS
        }
      ),
    error_messages = settings.DEMOS_SELENIUM_URL_FIELD_ERROR_MESSAGES
    )

  width = forms.IntegerField(
    label=settings.DEMOS_SELENIUM_WIDTH_FIELD_LABEL,
    initial=settings.DEMOS_SELENIUM_IMAGE_WIDTH_INITIAL,
    min_value=settings.DEMOS_SELENIUM_IMAGE_WIDTH_MIN,
    max_value=settings.DEMOS_SELENIUM_IMAGE_WIDTH_MAX,
    widget=forms.TextInput(
      attrs={
        'class': settings.DEMOS_SELENIUM_WIDTH_CLASS
        }
      ),
    error_messages = settings.DEMOS_SELENIUM_WIDTH_FIELD_ERROR_MESSAGES
    )

  height = forms.IntegerField(
    label=settings.DEMOS_SELENIUM_HEIGHT_FIELD_LABEL,
    initial=settings.DEMOS_SELENIUM_IMAGE_HEIGHT_INITIAL,
    min_value=settings.DEMOS_SELENIUM_IMAGE_HEIGHT_MIN,
    max_value=settings.DEMOS_SELENIUM_IMAGE_HEIGHT_MAX,
    widget=forms.TextInput(
      attrs={
        'class': settings.DEMOS_SELENIUM_HEIGHT_CLASS
        }
      ),
    error_messages = settings.DEMOS_SELENIUM_HEIGHT_FIELD_ERROR_MESSAGES
    )

  def __init__(self, user, *args, **kwargs):

    super(forms.Form, self).__init__(*args, **kwargs)
    self.user = user

    options = webdriver.ChromeOptions()

    options.add_argument("--headless")

    if settings.DEMOS_SELENIUM_PROXY:
      options.add_argument("--proxy-server=" + settings.DEMOS_SELENIUM_PROXY)

    self.options = options

    self.browser = webdriver.Chrome(
      settings.DEMOS_SELENIUM_CHROME_DRIVER_PATH,
      chrome_options=options,
      )

    if 'data' in kwargs: # form is bound
      new_data = kwargs['data'].copy() # can't modify form data

      if self.Fields.URL in kwargs['data']:
        self.fields[self.Fields.URL].initial = kwargs['data'][self.Fields.URL]

      else:
        self.fields[self.Fields.URL].initial = settings.DEMOS_SELENIUM_INITIAL_URL
        new_data[self.Fields.URL] = self.fields[self.Fields.URL].initial

      if self.Fields.WIDTH in kwargs['data']:
        self.fields[self.Fields.WIDTH].initial = kwargs['data'][self.Fields.WIDTH]

      else:
        self.fields[self.Fields.WIDTH].initial = settings.DEMOS_SELENIUM_IMAGE_WIDTH_INITIAL
        new_data[self.Fields.WIDTH] = self.fields[self.Fields.WIDTH].initial

      if self.Fields.HEIGHT in kwargs['data']:
        self.fields[self.Fields.HEIGHT].initial = kwargs['data'][self.Fields.HEIGHT]

      else:
        self.fields[self.Fields.HEIGHT].initial = settings.DEMOS_SELENIUM_IMAGE_HEIGHT_INITIAL
        new_data[self.Fields.HEIGHT] = self.fields[self.Fields.HEIGHT].initial

      self.data = new_data

  def process(self, *args, **kwargs):
    try:
      self.image = self.screenshot(
        self.cleaned_data[self.Fields.URL],
        self.cleaned_data[self.Fields.WIDTH],
        self.cleaned_data[self.Fields.HEIGHT])

    except Exception as e:
      self.add_error(
        forms.forms.NON_FIELD_ERRORS,
        self.error_messages[self.Errors.SELENIUM_DRIVER]
        )

  def screenshot(self, url, width, height, *args, **kwargs):
    self.browser.set_window_size(width, height)
    self.browser.get(url)
    png = self.browser.get_screenshot_as_png()
    stream = BytesIO(png)
    encoded_img = base64.b64encode(stream.getvalue()).decode("utf-8")
    return encoded_img
