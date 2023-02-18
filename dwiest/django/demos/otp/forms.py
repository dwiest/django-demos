from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _
import base64
from io import BytesIO
import pyotp
import qrcode
from ..conf import settings

class OtpForm(forms.Form):
  secret_key = forms.CharField(
    label='Secret Key',
    min_length="32",
    max_length="32",
    initial=settings.DEMOS_OTP_INITIAL_SECRET_KEY,
    required=False,
    widget=forms.TextInput(attrs={'class': settings.DEMOS_OTP_SECRET_KEY_CLASS})
    )

  name = forms.CharField(
    label='Name',
    initial=settings.DEMOS_OTP_QRCODE_PROVISIONING_NAME,
    required=False,
    widget=forms.TextInput(attrs={'class': settings.DEMOS_OTP_QRCODE_PROVISIONING_NAME_CLASS})
    )

  issuer_name = forms.CharField(
    label='Issuer',
    initial=settings.DEMOS_OTP_QRCODE_PROVISIONING_ISSUER,
    required=False,
    widget=forms.TextInput(attrs={'class': settings.DEMOS_OTP_QRCODE_PROVISIONING_ISSUER_CLASS})
    )

  error_messages = {
    'invalid_secret_key':
      _('The secret key is invalid, it must be 32 characters long.')
  }

  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)

    if 'data' not in kwargs: # form not bound
      secret_key = self.fields['secret_key'].initial

      if not secret_key:
        secret_key = OtpForm.get_secret_key()
        self.fields['secret_key'].initial = secret_key

      self.secret_key = secret_key
      self.otp = OtpForm.get_otp(secret_key)

      self.provisioning_uri = OtpForm.get_provisioning_uri(
        self.secret_key,
        self.fields['name'].initial,
        self.fields['issuer_name'].initial)

      self.qrcode = OtpForm.get_qrcode(self.provisioning_uri)

  def clean_secret_key(self):

    if not self.cleaned_data['secret_key']:
      secret_key = OtpForm.get_secret_key()
      new_data = self.data.copy()
      new_data['secret_key'] = secret_key
      self.data = new_data
      return secret_key

    elif len(self.cleaned_data['secret_key']) != 32:
        raise OtpForm.get_invalid_secret_key_error()

    else:
      return self.cleaned_data['secret_key']

  def process(self):
    self.secret_key = self.cleaned_data['secret_key']
    name = self.cleaned_data['name']
    issuer_name = self.cleaned_data['issuer_name']
    self.otp = OtpForm.get_otp(self.secret_key)
    self.provisioning_uri = OtpForm.get_provisioning_uri(self.secret_key, name, issuer_name)
    self.qrcode = OtpForm.get_qrcode(self.provisioning_uri)

  @classmethod
  def get_invalid_secret_key_error(cls):
    return ValidationError(
      cls.error_messages['invalid_secret_key'],
      code = 'invalid_secret_key')

  @classmethod
  def get_provisioning_uri(cls, secret_key, name, issuer_name):
    return pyotp.TOTP(secret_key).provisioning_uri(name=name, issuer_name=issuer_name)

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
