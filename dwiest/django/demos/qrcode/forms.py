from django import forms
import base64
import qrcode
from io import BytesIO

class QrcodeForm(forms.Form):
  input_text = forms.CharField(
    label='input_text',
    initial='')

  def get_qrcode(self):
    #data = "https://wiest.world/"
    qr = qrcode.QRCode(
      version=1,
      error_correction=qrcode.constants.ERROR_CORRECT_H,
      box_size=10,
      border=4
      )
    qr.add_data(self.cleaned_data['input_text'])
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert('RGB')
    #img.save("static/qrcode.png")
    stream = BytesIO()
    img.save(stream, format="PNG")
    encoded_img = base64.b64encode(stream.getvalue()).decode("utf-8")
    return encoded_img
