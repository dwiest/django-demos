import datetime
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django import forms
from django.utils.translation import ugettext, ugettext_lazy as _
from enum import Enum, auto
import hashlib
import pytz
from ..conf import settings
from ..templatetags.dwiest_django_demos.file import filters
from .models import File, FileQuota, FileSummary

class FileUploadForm(forms.Form):

  class Errors(str, Enum):
    SAVE_FAILED = auto()
    WRITE_FAILED = auto()
    TOO_MANY_FILES = auto()
    SIZE_TOO_LARGE = auto()
    TOTAL_SIZE_TOO_LARGE = auto()

  class Fields(str, Enum):
    FILE = 'file'

  error_messages = {
    Errors.SAVE_FAILED:
      _(settings.DEMOS_FILE_SAVE_FAILED_ERROR),
    Errors.WRITE_FAILED:
      _(settings.DEMOS_FILE_WRITE_FAILED_ERROR),
    Errors.TOO_MANY_FILES:
      _(settings.DEMOS_FILE_TOO_MANY_FILES_ERROR),
    Errors.SIZE_TOO_LARGE:
      _(settings.DEMOS_FILE_SIZE_TOO_LARGE_ERROR),
    Errors.TOTAL_SIZE_TOO_LARGE:
      _(settings.DEMOS_FILE_TOTAL_SIZE_TOO_LARGE_ERROR),
    }

  file = forms.FileField(
    widget = forms.ClearableFileInput(
      attrs={
        'class': settings.DEMOS_FILE_INPUT_CLASS
        }
      ),
    )

  def __init__(self, user, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.user = user

    # load file quota
    quotas = FileQuota.objects.filter(id=1)
    if len(quotas) == 1:
      self.quota = quotas[0]
    else:
      self.quota = None

    # load or create file summary
    if user.id: # logged in user
      owner = user
    else: # AnonymousUser
      owner = None

    summaries = FileSummary.objects.filter(owner=owner)

    if len(summaries) < 1: # none found, create one
      self.summary = FileSummary(owner=owner, files=0, size=0)
    elif len(summaries) == 1: # match
      self.summary = summaries[0]
    else: # shouldn't happen!
      print("Too many summaries for {}, found {}. Using first result.".format(user, len(summaries)))
      self.summary = summaries[0]

  def clean(self):
    if self.quota:
      file = self.cleaned_data.get(self.Fields.FILE)

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
    file = self.cleaned_data.get(self.Fields.FILE)

    if self.user and self.user.id:
      owner = self.user
    else:
      owner = None

    model = File(
      owner=owner,
      name=file.name,
      content_type=file.content_type,
      size=file.size,
      versioned=False,
      downloadable=False)

    try:
      print("writing to: " + model.path)
      hash_md5 = hashlib.md5()
      hash_sha256 = hashlib.sha256()
      #FIXME check that path doesn't already exist
      file_dir = settings.DEMOS_FILE_UPLOAD_DIR

      with open(file_dir + '/' + model.path, 'wb+') as output:
        for chunk in file.chunks():
          hash_md5.update(chunk)
          hash_sha256.update(chunk)
          output.write(chunk)

      model.md5_checksum = hash_md5.hexdigest()
      model.sha256_checksum = hash_sha256.hexdigest()
      self.summary.files += 1
      self.summary.size += file.size
      self.file = model

    except Exception as e:
      print(str(e))
      raise self.get_write_failed_error()

    try:
      model.save()
      self.summary.save()

    except Exception as e:
      print(str(e))
      raise self.get_save_failed_error()

  @classmethod
  def get_save_failed_error(cls):
    return forms.ValidationError(
      cls.error_messages[cls.Errors.SAVE_FAILED],
      code=cls.Errors.SAVE_FAILED
      )

  @classmethod
  def get_write_failed_error(cls):
    return forms.ValidationError(
      cls.error_messages[cls.Errors.WRITE_FAILED],
      code=cls.Errors.WRITE_FAILED
      )

  @classmethod
  def get_file_quota_error(cls):
    return forms.ValidationError(
      cls.error_messages[cls.Errors.TOO_MANY_FILES],
      code=cls.Errors.TOO_MANY_FILES
      )

  @classmethod
  def get_filesize_quota_error(cls, bytes):
    return forms.ValidationError(
      cls.error_messages[cls.Errors.SIZE_TOO_LARGE].format(filters.format_bytes(bytes,2)),
      code=cls.Errors.SIZE_TOO_LARGE
      )

  @classmethod
  def get_total_filesize_quota_error(cls, bytes):
    return forms.ValidationError(
      cls.error_messages[self.Errors.TOTAL_SIZE_TOO_LARGE].format(filters.format_bytes(bytes,2)),
      code=self.Errors.TOTAL_SIZE_TOO_LARGE
      )


class FileDetailsForm(forms.ModelForm):
  class Meta:
    model = File
    fields = ['name','versioned','description']
    widgets = {
      'name': forms.TextInput(attrs={'class': settings.DEMOS_FILE_NAME_INPUT_CLASS}),
      'description': forms.Textarea(attrs={'class': settings.DEMOS_FILE_DESCRIPTION_INPUT_CLASS}),
      }
