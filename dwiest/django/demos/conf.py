from appconf import AppConf
from django.conf import settings
from django.utils.translation import gettext_lazy as _
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
  FILE_SAVE_FAILED_ERROR = "Couldn't update database."
  FILE_WRITE_FAILED_ERROR = "Couldn't write file."
  FILE_TOO_MANY_FILES_ERROR = 'You have reached your limit for file uploads.'
  FILE_SIZE_TOO_LARGE_ERROR = 'File size exceeds the maximum allowed by {}.'
  FILE_TOTAL_SIZE_TOO_LARGE_ERROR = 'You will exceed your limit for total file size by {}.'

  ''' Google reCAPTCHA demo settings '''

  GOOGLE_RECAPTCHA_PROJECT_ID = None
  GOOGLE_RECAPTCHA_SITE_KEY = None
  GOOGLE_RECAPTCHA_TEMPLATE = 'dwiest-django-demos/grecaptcha/index.html'

  ''' One-time password demo settings '''
  OTP_SECRET_KEY = ''
  OTP_QRCODE_NAME = ''
  OTP_QRCODE_NAME_CLASS = 'provisioning-name'
  OTP_QRCODE_ISSUER = ''
  OTP_QRCODE_ISSUER_CLASS = 'provisioning-issuer'
  OTP_QRCODE_VERSION = 1
  OTP_QRCODE_ERROR_CORRECTION = constants.ERROR_CORRECT_H
  OTP_QRCODE_BOX_SIZE = 5
  OTP_QRCODE_BORDER = 4
  OTP_QRCODE_FILL_COLOR = 'black'
  OTP_QRCODE_BACKGROUND_COLOR = 'white'
  OTP_QRCODE_FORMAT = 'PNG'
  OTP_SECRET_KEY_CLASS = 'secret-key'
  OTP_TEMPLATE = 'dwiest-django-demos/otp/index.html'
  OTP_SECRET_KEY_LABEL = 'Secret Key'
  OTP_SECRET_KEY_LENGTH = 32
  OTP_NAME_LABEL = 'Name'
  OTP_ISSUER_LABEL = 'Issuer'
  OTP_SECRET_KEY_INVALID_ERROR = 'The secret key is invalid, it must be 32 characters long.'

  ''' QR code demo settings '''
  QRCODE_TEMPLATE = 'dwiest-django-demos/qrcode/index.html'
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
  QRCODE_TEXT_INPUT_LABEL = 'Text'

  ''' Selenium demo settings '''
  SELENIUM_INITIAL_URL = 'https://github.com/dwiest/django-demos/'
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
  SELENIUM_HEIGHT_FIELD_ERROR_MESSAGES = {
    'max_value': _('The image height must be less than or equal to %(limit_value)s.'),
    'min_value': _('The image height must be greather than or equal to %(limit_value)s.'),
    'required': _('An image height is required.'),
    }
  SELENIUM_HEIGHT_FIELD_LABEL = 'Height'
  SELENIUM_URL_CLASS = 'selenium-url'
  SELENIUM_URL_FIELD_ERROR_MESSAGES = {
    'invalid': _('Please enter a valid URL.'),
    'required': _('Please provide a URL.'),
    }
  SELENIUM_URL_FIELD_LABEL = 'URL'
  SELENIUM_URL_INVALID_ERROR_MESSAGE = 'The URL provided is not valid'
  SELENIUM_URL_MISSING_SCHEME_ERROR_MESSAGE = 'The URL provided does not have a scheme, e.g. https://'
  SELENIUM_WIDTH_CLASS = 'selenium-width'
  SELENIUM_WIDTH_FIELD_LABEL = 'Width'
  SELENIUM_WIDTH_FIELD_ERROR_MESSAGES = {
    'max_value': _('The image width must be less than or equal to %(limit_value)s.'),
    'min_value': _('The image width must be greather than or equal to %(limit_value)s.'),
    'required': _('An image width is required.'),
    }
  SELENIUM_DRIVER_ERROR_MESSAGE = 'Selenium encountered an error while processing your request.'
