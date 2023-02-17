from django import forms
import base64
import qrcode
from io import BytesIO
from ..conf import settings

class QrcodeForm(forms.Form):
  input_text = forms.CharField(
    label='Text',
    initial=settings.DEMOS_QRCODE_INITIAL_TEXT,
    widget=forms.TextInput(attrs={'class': settings.DEMOS_QRCODE_INPUT_CLASS}),
    )

  def get_qrcode(self):
    qr = qrcode.QRCode(
      version=settings.DEMOS_QRCODE_VERSION,
      error_correction=settings.DEMOS_QRCODE_ERROR_CORRECTION,
      box_size=settings.DEMOS_QRCODE_BOX_SIZE,
      border=settings.DEMOS_QRCODE_BORDER,
      )
    qr.add_data(self.cleaned_data['input_text'])
    qr.make(fit=True)
    img = qr.make_image(fill_color=settings.DEMOS_QRCODE_FILL_COLOR, back_color=settings.DEMOS_QRCODE_BACKGROUND_COLOR).convert('RGB')
    stream = BytesIO()
    img.save(stream, format=settings.DEMOS_QRCODE_FORMAT)
    encoded_img = base64.b64encode(stream.getvalue()).decode("utf-8")
    return encoded_img
