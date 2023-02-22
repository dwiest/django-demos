from django import forms
from enum import Enum
from selenium import webdriver
from ..conf import settings
import base64
from io import BytesIO


class SeleniumForm(forms.Form):
  class Fields(str, Enum):
    HEIGHT = 'height',
    URL = 'url',
    WIDTH = 'width',

  url = forms.URLField(
    label=settings.DEMOS_SELENIUM_URL_FIELD_LABEL,
    initial=settings.DEMOS_SELENIUM_INITIAL_URL,
    widget=forms.TextInput(
      attrs={
        'class': settings.DEMOS_SELENIUM_URL_CLASS
        }
      ),
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
    )

  def __init__(self, user,
    url=settings.DEMOS_SELENIUM_INITIAL_URL,
    width=settings.DEMOS_SELENIUM_IMAGE_WIDTH_INITIAL,
    height=settings.DEMOS_SELENIUM_IMAGE_HEIGHT_INITIAL,
    *args, **kwargs):

    super(forms.Form, self).__init__(*args, **kwargs)
    self.user = user

    options = webdriver.ChromeOptions()

    options.add_argument("--headless")

    if settings.DEMOS_SELENIUM_PROXY != None:
      options.add_argument("--proxy-server=" + settings.DEMOS_SELENIUM_PROXY)

    self.options = options

    self.browser = webdriver.Chrome(
      settings.DEMOS_SELENIUM_CHROME_DRIVER_PATH,
      chrome_options=options,
      )

    if 'data' not in kwargs: # form not bound
      self.fields[self.Fields.URL].initial = url
      self.fields[self.Fields.WIDTH].initial = width
      self.fields[self.Fields.HEIGHT].initial = height

    self.image = self.screenshot(url, width, height)

  def process(self, *args, **kwargs):
    self.image = self.screenshot(
      self.cleaned_data[self.Fields.URL],
      self.cleaned_data[self.Fields.WIDTH],
      self.cleaned_data[self.Fields.HEIGHT])

  def screenshot(self, url, width, height, *args, **kwargs):
    self.browser.set_window_size(width, height)
    self.browser.get(url)
    png = self.browser.get_screenshot_as_png()
    stream = BytesIO(png)
    encoded_img = base64.b64encode(stream.getvalue()).decode("utf-8")
    return encoded_img
