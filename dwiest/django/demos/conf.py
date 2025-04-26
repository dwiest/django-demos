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

  ''' Booksmarks demo settings '''
  BOOKMARKS_ARTICLE_DATE_CLASS = 'article-date'
  BOOKMARKS_BOOKMARK_TEMPLATE = 'dwiest-django-demos/bookmarks/bookmark.html'
  BOOKMARKS_CREATED_AT_CLASS = 'created-at'
  BOOKMARKS_CREATED_AT_LABEL = 'Created'
  BOOKMARKS_DESCRIPTION_CLASS = 'description'
  BOOKMARKS_DESCRIPTION_LABEL = 'Description'
  BOOKMARKS_DUPLICATE_URL_ERROR = 'A bookmark already exists for that URL.'
  BOOKMARKS_FILTER_CLASS = 'filter'
  BOOKMARKS_EXPORT_TEMPLATE = 'dwiest-django-demos/bookmarks/export.html'
  BOOKMARKS_LAST_MODIFIED_CLASS = 'last-modified'
  BOOKMARKS_LAST_MODIFIED_LABEL = 'Last Modified'
  BOOKMARKS_STATUS_CLASS = 'status'
  BOOKMARKS_STATUS_LABEL = 'Status'
  BOOKMARKS_TEMPLATE = 'dwiest-django-demos/bookmarks/home.html'
  BOOKMARKS_TITLE_CLASS = 'title'
  BOOKMARKS_TITLE_LABEL = 'Title'
  BOOKMARKS_UNREAD_CLASS = 'unread'
  BOOKMARKS_UNREAD_LABEL = 'To Read'
  BOOKMARKS_URL_DEFAULT = None
  BOOKMARKS_URL_LABEL = 'URL'
  BOOKMARKS_URL_CLASS = 'url'
  BOOKMARKS_TAG_BOOKMARK_TEMPLATE = 'dwiest-django-demos/bookmarks/tags/bookmark.html'
  BOOKMARKS_TAG_TEMPLATE = 'dwiest-django-demos/bookmarks/tags/view.html'
  BOOKMARKS_TAG_EDIT_TEMPLATE = 'dwiest-django-demos/bookmarks/tags/edit.html'
  BOOKMARKS_TAGS_TEMPLATE = 'dwiest-django-demos/bookmarks/tags/index.html'

  ''' Expense Tracker demo settings '''
  EXPENSES_EXPENSE_TEMPLATE = 'dwiest-django-demos/expenses/home.html'
  EXPENSES_EXPENSE_EDIT_TEMPLATE = 'dwiest-django-demos/expenses/home.html'
  EXPENSES_EXPENSE_LIST_TEMPLATE = 'dwiest-django-demos/expenses/list/view.html'
  EXPENSES_EXPENSE_LIST_EDIT_TEMPLATE = 'dwiest-django-demos/expenses/list/edit.html'
  EXPENSES_EXPENSE_CATEGORY_TEMPLATE = 'dwiest-django-demos/expenses/category/view.html'
  EXPENSES_EXPENSE_CATEGORY_EDIT_TEMPLATE = 'dwiest-django-demos/expenses/category/edit.html'

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

  ''' Inventory demo settings '''
  INVENTORY_LIST_HOME_TEMPLATE = 'dwiest-django-demos/inventory/home.html'
  INVENTORY_LIST_VIEW_TEMPLATE = 'dwiest-django-demos/inventory/list/view.html'
  INVENTORY_LIST_EDIT_TEMPLATE = 'dwiest-django-demos/inventory/list/edit.html'
  INVENTORY_ITEM_VIEW_TEMPLATE = 'dwiest-django-demos/inventory/item/view.html'
  INVENTORY_ITEM_EDIT_TEMPLATE = 'dwiest-django-demos/inventory/item/edit.html'
  INVENTORY_ENTRY_VIEW_TEMPLATE = 'dwiest-django-demos/inventory/entry/view.html'
  INVENTORY_ENTRY_EDIT_TEMPLATE = 'dwiest-django-demos/inventory/entry/edit.html'

  ''' Invoice demo settings '''
  INVOICER_BILL_TO_TEMPLATE = 'dwiest-django-demos/invoicer/bill_to/view.html'
  INVOICER_BILL_TO_EDIT_TEMPLATE = 'dwiest-django-demos/invoicer/bill_to/edit.html'
  INVOICER_BILL_TO_LIST_TEMPLATE = 'dwiest-django-demos/invoicer/bill_to/index.html'
  INVOICER_INVOICE_TEMPLATE = 'dwiest-django-demos/invoicer/invoice/view.html'
  INVOICER_INVOICE_EDIT_TEMPLATE = 'dwiest-django-demos/invoicer/invoice/edit.html'
  INVOICER_INVOICE_LIST_TEMPLATE = 'dwiest-django-demos/invoicer/invoice/index.html'
  INVOICER_INVOICE_RENDER_TEMPLATE = 'dwiest-django-demos/invoicer/invoice/render.html'

  ''' Journal demo settings '''
  JOURNAL_LIST_TEMPLATE = 'dwiest-django-demos/journal/index.html'
  JOURNAL_TEMPLATE = 'dwiest-django-demos/journal/journal.html'
  JOURNAL_EDIT_TEMPLATE = 'dwiest-django-demos/journal/journal_edit.html'
  JOURNAL_ENTRY_TEMPLATE = 'dwiest-django-demos/journal/entry.html'
  JOURNAL_ENTRY_EDIT_TEMPLATE = 'dwiest-django-demos/journal/entry_edit.html'
  JOURNAL_DUPLICATE_NAME_ERROR = 'That name is already in use.'
  JOURNAL_NAME_LABEL = 'Name'
  JOURNAL_NAME_CLASS = 'journal_name'
  JOURNAL_NAME_DEFAULT = 'My Journal'
  JOURNAL_DUPLICATE_DATE_ERROR = 'There is already a journal entry for that date'

  ''' News settings '''

  NEWS_ITEM_LIST_TEMPLATE = 'dwiest-django-demos/news/index.html'
  NEWS_ITEM_TEMPLATE = 'dwiest-django-demos/news/item.html'
  NEWS_ITEM_EDIT_TEMPLATE = 'dwiest-django-demos/news/edit.html'
  NEWS_ITEM_DELETE_TEMPLATE = 'dwiest-django-demos/news/delete.html'

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
  SELENIUM_PROXY = 'squid:3128'
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
