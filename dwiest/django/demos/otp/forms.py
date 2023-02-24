from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _
import base64
from enum import Enum, auto
from io import BytesIO
import pyotp
import qrcode
from ..conf import settings

class OtpForm(forms.Form):

  class Fields(str, Enum):
    ISSUER= 'issuer'
    NAME = 'name'
    SECRET_KEY = 'secret_key'

  class Errors(str, Enum):
    SECRET_KEY_INVALID = auto()

  error_messages = {
    Errors.SECRET_KEY_INVALID:
      _(settings.DEMOS_OTP_SECRET_KEY_INVALID_ERROR),
  }

  form_field_defaults = {
    Fields.ISSUER: settings.DEMOS_OTP_QRCODE_ISSUER,
    Fields.NAME: settings.DEMOS_OTP_QRCODE_NAME,
    Fields.SECRET_KEY: settings.DEMOS_OTP_SECRET_KEY,
  }

  secret_key = forms.CharField(
    label=settings.DEMOS_OTP_SECRET_KEY_LABEL,
    min_length=settings.DEMOS_OTP_SECRET_KEY_LENGTH,
    max_length=settings.DEMOS_OTP_SECRET_KEY_LENGTH,
    initial=settings.DEMOS_OTP_SECRET_KEY,
    required=False,
    widget=forms.TextInput(
      attrs={
        'class': settings.DEMOS_OTP_SECRET_KEY_CLASS
        }
      )
    )

  name = forms.CharField(
    label=settings.DEMOS_OTP_NAME_LABEL,
    initial=settings.DEMOS_OTP_QRCODE_NAME,
    required=False,
    widget=forms.TextInput(
      attrs={
        'class': settings.DEMOS_OTP_QRCODE_NAME_CLASS
        }
      )
    )

  issuer = forms.CharField(
    label=settings.DEMOS_OTP_ISSUER_LABEL,
    initial=settings.DEMOS_OTP_QRCODE_ISSUER,
    required=False,
    widget=forms.TextInput(
      attrs={
        'class': settings.DEMOS_OTP_QRCODE_ISSUER_CLASS
        }
      )
    )

  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)

    if 'data' in kwargs: # form is bound
      new_data = kwargs['data'].copy() # can't modify form data

      for field, default_value in self.form_field_defaults.items():
        if field in kwargs['data']:
          self.fields[field].initial = kwargs['data'][field]
        else:
          self.fields[field].initial = default_value
          new_data[field] = default_value

      # auto-generate a secret key if one is not set
      if not self.fields[self.Fields.SECRET_KEY].initial:
        new_data[self.Fields.SECRET_KEY] = OtpForm.get_secret_key()

      self.data = new_data

  def clean_secret_key(self):
    secret_key = self.cleaned_data[self.Fields.SECRET_KEY]

    if len(secret_key) != settings.DEMOS_OTP_SECRET_KEY_LENGTH:
        raise OtpForm.get_invalid_secret_key_error()
    else:
      return secret_key

  def process(self):
    self.otp = OtpForm.get_otp(self.cleaned_data[self.Fields.SECRET_KEY])

    provisioning_uri = OtpForm.get_provisioning_uri(
      self.cleaned_data[self.Fields.SECRET_KEY],
      self.cleaned_data[self.Fields.NAME],
      self.cleaned_data[self.Fields.ISSUER])

    self.qrcode = OtpForm.get_qrcode(provisioning_uri)

  @classmethod
  def get_invalid_secret_key_error(cls):
    return ValidationError(
      cls.error_messages[cls.Errors.SECRET_KEY_INVALID],
      code = cls.Errors.SECRET_KEY_INVALID)

  @classmethod
  def get_provisioning_uri(cls, secret_key, name, issuer):
    return pyotp.TOTP(secret_key).provisioning_uri(name=name, issuer_name=issuer)

  @classmethod
  def get_secret_key(cls):
    return pyotp.random_base32()

  @classmethod
  def get_otp(cls, secret_key):
    totp = pyotp.TOTP(secret_key)
    return totp.now()

  @classmethod
  def get_qrcode(cls, text):
    qr = qrcode.QRCode(
      version=settings.DEMOS_OTP_QRCODE_VERSION,
      error_correction=settings.DEMOS_OTP_QRCODE_ERROR_CORRECTION,
      box_size=settings.DEMOS_OTP_QRCODE_BOX_SIZE,
      border=settings.DEMOS_OTP_QRCODE_BORDER
    )

    qr.add_data(text)
    qr.make(fit=True)

    img = qr.make_image(
      fill_color=settings.DEMOS_OTP_QRCODE_FILL_COLOR,
      back_color=settings.DEMOS_OTP_QRCODE_BACKGROUND_COLOR
      ).convert('RGB')

    stream = BytesIO()
    img.save(stream, format=settings.DEMOS_OTP_QRCODE_FORMAT)
    encoded_img = base64.b64encode(stream.getvalue()).decode("utf-8")
    return encoded_img
