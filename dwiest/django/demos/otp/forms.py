from django import forms
import base64
from io import BytesIO
import pyotp
import qrcode
from ..conf import settings

class OtpForm(forms.Form):
  secret_key = forms.CharField(
    label='secret_key',
    min_length="32",
    max_length="32",
    initial=settings.DEMOS_OTP_INITIAL_SECRET_KEY,
    required=False,
    widget=forms.TextInput(attrs={'size': '38'}))

  name = forms.CharField(
    label='name',
    initial=settings.DEMOS_OTP_QRCODE_PROVISIONING_NAME,
    required=False,
    widget=forms.TextInput(attrs={'size': '12'}))

  issuer_name = forms.CharField(
    label='issuer_name',
    initial=settings.DEMOS_OTP_QRCODE_PROVISIONING_ISSUER,
    required=False,
    widget=forms.TextInput(attrs={'size': '12'}))

  def clean_secret_key(self):
    if self.cleaned_data['secret_key'] == '':
      secret_key = pyotp.random_base32()
      new_data = self.data.copy()
      new_data['secret_key'] = secret_key
      self.data = new_data
      return secret_key
    else:
      return self.cleaned_data['secret_key']

  def get_otp(self):
    totp = pyotp.TOTP(self.cleaned_data['secret_key'])
    return totp.now()

  def get_provisioning_uri(self):
    return pyotp.TOTP(self.cleaned_data['secret_key']).provisioning_uri(name=self.cleaned_data['name'], issuer_name=self.cleaned_data['issuer_name'])

def get_qrcode(text):
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
