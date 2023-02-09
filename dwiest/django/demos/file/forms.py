import datetime
import pytz

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django import forms
from django.utils.translation import ugettext, ugettext_lazy as _

from ..conf import settings
from .models import File


class FileUploadForm(forms.Form):
  file = forms.FileField()
#    widget=forms.ClearableFileInput(
#      attrs={
#        'multiple': True
#        }
#      )
#    )

  error_messages = {
    'save_failed':
      _("Couldn't update database."),
    'write_failed':
      _("Couldn't write file."),
    }

  def __init__(self, user=None, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.user = user

  def clean(self):
    return super().clean()

  def save(self):
    file = self.cleaned_data.get('file')

    model = File(owner=self.user, name=file.name, content_type=file.content_type, size=file.size, versioned=False, downloadable=False)

    try:
      print("writing to: " + model.path)
      #FIXME check that path doesn't already exist
      with open('/tmp/' + model.path, 'wb+') as output:
        for chunk in file.chunks():
          output.write(chunk)
    except Exception as e:
      print(str(e))
      raise self.get_write_failed_error()

    try:
      model.save()
    except Exception as e:
      print(str(e))
      raise self.get_save_failed_error()

  def get_save_failed_error(self):
    return forms.ValidationError(
      self.error_messages['save_failed'],
      code='save_failed',)

  def get_write_failed_error(self):
    return forms.ValidationError(
      self.error_messages['save_failed'],
      code='save_failed',)
