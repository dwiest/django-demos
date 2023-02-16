from django import forms
from selenium import webdriver
from ..conf import settings


class SeleniumForm(forms.Form):
  url = forms.URLField(
    label='url',
    initial=settings.DEMOS_SELENIUM_INITIAL_URL,
    widget=forms.TextInput(attrs={'size': settings.DEMOS_SELENIUM_INPUT_SIZE}),
    )

  width = forms.IntegerField(
    label='Width',
    initial=settings.DEMOS_SELENIUM_IMAGE_WIDTH_INITIAL,
    min_value=settings.DEMOS_SELENIUM_IMAGE_WIDTH_MIN,
    max_value=settings.DEMOS_SELENIUM_IMAGE_WIDTH_MAX,
    )

  height = forms.IntegerField(
    label='Height',
    initial=settings.DEMOS_SELENIUM_IMAGE_HEIGHT_INITIAL,
    min_value=settings.DEMOS_SELENIUM_IMAGE_HEIGHT_MIN,
    max_value=settings.DEMOS_SELENIUM_IMAGE_HEIGHT_MAX,
    )

  def __init__(self, user, width=None, height=None, *args, **kwargs):
    super(forms.Form, self).__init__(*args, **kwargs)
    self.user = user

    if width:
      self.fields['width'].initial = width
    if height:
      self.fields['height'].initial = height

    options = webdriver.ChromeOptions()

    options.add_argument("--headless")

    if settings.DEMOS_SELENIUM_PROXY != None:
      options.add_argument("--proxy-server=" + settings.DEMOS_SELENIUM_PROXY)

    self.options = options

    self.browser = webdriver.Chrome(
      settings.DEMOS_SELENIUM_CHROME_DRIVER_PATH,
      chrome_options=options,
      )

  def screenshot(self, *args, **kwargs):
    self.browser.set_window_size(self.cleaned_data['width'],self.cleaned_data['height'])
    self.browser.get(self.cleaned_data['url'])
    screenshot_file = str(self.user) + '-screenie.png'
    self.browser.save_screenshot(settings.DEMOS_SELENIUM_SCREENSHOT_DIR + '/' + screenshot_file)
