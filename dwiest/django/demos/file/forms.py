import datetime
import hashlib
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
      hash_md5 = hashlib.md5()
      hash_sha256 = hashlib.sha256()
      #FIXME check that path doesn't already exist
      with open('/tmp/' + model.path, 'wb+') as output:
        for chunk in file.chunks():
          hash_md5.update(chunk)
          hash_sha256.update(chunk)
          output.write(chunk)
      model.md5_checksum = hash_md5.hexdigest()
      model.sha256_checksum = hash_sha256.hexdigest()
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


class FileDetailsForm(forms.ModelForm):
  class Meta:
    model = File
    #fields = ['path','name','versioned','description']
    #exclude = ['owner','content_type','size','created_at','downloadable','human_readable_size']
    fields = ['name','versioned','description']
    exclude = ['path', 'content_type','downloadable', 'created_at', 'size', 'owner']
    widgets = {
      'description': forms.Textarea(attrs={'cols':72, 'rows':4}),
      }
