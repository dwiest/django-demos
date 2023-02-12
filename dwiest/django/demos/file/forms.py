import datetime
import hashlib
import pytz

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django import forms
from django.utils.translation import ugettext, ugettext_lazy as _

from ..conf import settings
from ..templatetags.file import filters
from .models import File, FileQuota, FileSummary


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
    'too_many_files':
      _("You have reached your limit for file uploads."),
    'filesize_too_large':
      _("File size exceeds the maximum allowed by {}."),
    'total_filesize_too_large':
      _("You will exceed your limit for total file size by {}."),
    }

  def __init__(self, user=None, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.user = user

    # load file quota
    quotas = FileQuota.objects.filter(id=1)
    if len(quotas) == 1:
      self.quota = quotas[0]
    else:
      self.quota = None

    # load file summary
    summaries = FileSummary.objects.filter(owner=user)
    if len(summaries) == 1:
      self.summary = summaries[0]
    else:
      self.summary = FileSummary(owner=user, files=0, size=0)

  def clean(self):
    if self.quota:
      file = self.cleaned_data.get('file')

      # check that not over number of file quota
      if self.summary.files >= self.quota.max_files:
        raise self.get_file_quota_error()

      # check that file is not over file size quota
      if self.quota.max_filesize > 0 and file.size > self.quota.max_filesize:
        exceeds_by = abs(self.quota.max_filesize - file.size)
        raise self.get_filesize_quota_error(exceeds_by)

      # check that not over total file size quota
      if self.summary.size + file.size > self.quota.max_total_filesize:
        exceeds_by = abs(self.quota.max_total_filesize - self.summary.size - file.size)
        raise self.get_total_filesize_quota_error(exceeds_by)

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
      self.summary.files += 1
      self.summary.size += file.size
    except Exception as e:
      print(str(e))
      raise self.get_write_failed_error()

    try:
      model.save()
      self.summary.save()
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

  def get_file_quota_error(self):
    return forms.ValidationError(
      self.error_messages['too_many_files'],
      code='too_many_files',)

  def get_filesize_quota_error(self, bytes):
    return forms.ValidationError(
      self.error_messages['filesize_too_large'].format(filters.format_bytes(bytes,2)),
      code='filesize_too_large',)

  def get_total_filesize_quota_error(self, bytes):
    return forms.ValidationError(
      self.error_messages['total_filesize_too_large'].format(filters.format_bytes(bytes,2)),
      code='total_filesize_too_large',)


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
