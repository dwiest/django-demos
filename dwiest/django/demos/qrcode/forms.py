import base64
from django import forms
from enum import Enum
from io import BytesIO
import qrcode
from ..conf import settings

class QrcodeForm(forms.Form):

  class Fields(str, Enum):
    TEXT = 'text'

  text = forms.CharField(
    label=settings.DEMOS_QRCODE_TEXT_INPUT_LABEL,
    initial=settings.DEMOS_QRCODE_INITIAL_TEXT,
    required=False,
    widget=forms.TextInput(
      attrs={
        'class': settings.DEMOS_QRCODE_INPUT_CLASS
        }
      ),
    )

  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)

    text = self.fields[self.Fields.TEXT].initial

    if 'data' in kwargs: # bound form
      if self.Fields.TEXT not in kwargs['data']:
        new_data = kwargs['data'].copy()
        new_data[self.Fields.TEXT] = text
        self.data = new_data

      else:
        text = kwargs['data'][self.Fields.TEXT]

    if text:
      self.qrcode = self.get_qrcode(text)

    else:
      self.qrcode = None

  def process(self):
    self.qrcode = self.get_qrcode(self.cleaned_data[self.Fields.TEXT])

  def get_qrcode(self, text):
    qr = qrcode.QRCode(
      version=settings.DEMOS_QRCODE_VERSION,
      error_correction=settings.DEMOS_QRCODE_ERROR_CORRECTION,
      box_size=settings.DEMOS_QRCODE_BOX_SIZE,
      border=settings.DEMOS_QRCODE_BORDER,
      )

    qr.add_data(text)
    qr.make(fit=True)

    img = qr.make_image(
      fill_color=settings.DEMOS_QRCODE_FILL_COLOR,
      back_color=settings.DEMOS_QRCODE_BACKGROUND_COLOR,
      ).convert('RGB')

    stream = BytesIO()
    img.save(stream, format=settings.DEMOS_QRCODE_FORMAT)
    encoded_img = base64.b64encode(stream.getvalue()).decode("utf-8")
    return encoded_img
