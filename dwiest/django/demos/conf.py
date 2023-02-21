from appconf import AppConf
from django.conf import settings
from qrcode import constants

class DemosAppConf(AppConf):

  def ready(self):
    from .files import signals
    pass

  ''' Django page template settings '''
  PAGE_FOOTER = None

  ''' File demo settings '''

  FILE_UPLOAD_DIR = '/tmp'
  FILE_INDEX_TEMPLATE = 'dwiest-django-demos/file/index.html'
  FILE_INPUT_CLASS = 'file'
  FILE_NAME_INPUT_CLASS = 'name-input'
  FILE_DESCRIPTION_INPUT_CLASS = 'description-input'
  FILE_DETAILS_TEMPLATE = 'dwiest-django-demos/file/details.html'

  ''' Google reCAPTCHA demo settings '''

  GOOGLE_RECAPTCHA_PROJECT_ID = None
  GOOGLE_RECAPTCHA_SITE_KEY = None
  GOOGLE_RECAPTCHA_TEMPLATE = 'dwiest-django-demos/grecaptcha/index.html'

  ''' One-time password demo settings '''
  OTP_INITIAL_SECRET_KEY = ''
  OTP_QRCODE_PROVISIONING_NAME = ''
  OTP_QRCODE_PROVISIONING_NAME_CLASS = 'provisioning-name'
  OTP_QRCODE_PROVISIONING_ISSUER = ''
  OTP_QRCODE_PROVISIONING_ISSUER_CLASS = 'provisioning-issuer'
  OTP_QRCODE_VERSION = 1
  OTP_QRCODE_ERROR_CORRECTION = constants.ERROR_CORRECT_H
  OTP_QRCODE_BOX_SIZE = 5
  OTP_QRCODE_BORDER = 4
  OTP_QRCODE_FILL_COLOR = 'black'
  OTP_QRCODE_BACKGROUND_COLOR = 'white'
  OTP_QRCODE_FORMAT = 'PNG'
  OTP_SECRET_KEY_CLASS = 'secret-key'
  OTP_TEMPLATE = 'dwiest-django-demos/otp/index.html'

  ''' QR code demo settings '''
  QRCODE_INITIAL_TEXT = 'https://github.com/dwiest/django-demos/'
  QRCODE_INPUT_CLASS = 'qrcode-input'
  QRCODE_VERSION = 1
  QRCODE_ERROR_CORRECTION = constants.ERROR_CORRECT_H
  QRCODE_BOX_SIZE = 10
  QRCODE_BORDER = 4
  QRCODE_FILL_COLOR = 'black'
  QRCODE_BACKGROUND_COLOR = 'white'
  QRCODE_FORMAT = 'PNG'
  QRCODE_TEMPLATE = 'dwiest-django-demos/qrcode/index.html'

  ''' Selenium demo settings '''
  SELENIUM_INITIAL_URL = 'https://github.com/dwiest/django-demos'
  SELENIUM_IMAGE_HEIGHT_INITIAL = 640
  SELENIUM_IMAGE_HEIGHT_MIN = 20
  SELENIUM_IMAGE_HEIGHT_MAX =  3072
  SELENIUM_IMAGE_WIDTH_INITIAL = 1280
  SELENIUM_IMAGE_WIDTH_MIN = 20
  SELENIUM_IMAGE_WIDTH_MAX =  2048
  SELENIUM_INPUT_SIZE = 40
  SELENIUM_PROXY = None
  SELENIUM_CHROME_DRIVER_PATH = '/usr/bin/chromedriver'
  SELENIUM_SCREENSHOT_DIR = '/tmp'
  SELENIUM_TEMPLATE = 'dwiest-django-demos/selenium/index.html'
  SELENIUM_HEIGHT_CLASS = 'selenium-height'
  SELENIUM_URL_CLASS = 'selenium-url'
  SELENIUM_WIDTH_CLASS = 'selenium-width'
