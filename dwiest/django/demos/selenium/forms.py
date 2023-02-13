from django import forms
from selenium import webdriver
from django.conf import settings


class SeleniumForm(forms.Form):
  url = forms.URLField(label='url',initial='')
  width = forms.IntegerField(label='width', initial='1024', min_value=20, max_value=2048)
  height = forms.IntegerField(label='height', initial='1024', min_value=20, max_value=3072)

  def __init__(self, user, *args, **kwargs):
    self.user = user
    options = webdriver.ChromeOptions()

    options.add_argument("--headless")

    if hasattr(settings, 'SELENIUM_PROXY'):
      options.add_argument("--proxy-server=" + settings.SELENIUM_PROXY)

    self.options = options
    self.browser = webdriver.Chrome('/usr/bin/chromedriver', chrome_options=options)

    super(forms.Form, self).__init__(*args, **kwargs)

  def screenshot(self, *args, **kwargs):
    self.browser.set_window_size(self.cleaned_data['width'],self.cleaned_data['height'])
    self.browser.get(self.cleaned_data['url'])
    self.browser.save_screenshot('/home/ec2-user/django-wiest.world/static/' + str(self.user) + '-screenie.png')
    
