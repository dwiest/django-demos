import uuid

from django.contrib.auth.models import User
from django.db import models


class File(models.Model):
  '''
    A file that was uploaded and is possibly available for download.
  '''
  owner = models.ForeignKey(
    User, on_delete=models.PROTECT)

  name = models.CharField(max_length=255)
  path = models.CharField(max_length=36)

  content_type = models.CharField(max_length=32)
#  type = models.ForeignKey(
#    'ContentType', on_delete=models.PROTECT)

  size = models.IntegerField() # bytes
  created_at = models.DateTimeField(auto_now_add=True)
  versioned = models.BooleanField(default=False)
  description = models.TextField(blank=True, null=True)
  downloadable = models.BooleanField(default=False)
  md5_checksum = models.CharField(max_length=32)
  sha256_checksum = models.CharField(max_length=64)

  def __init__(self, *args, **kwargs):
    super().__init__(*args,**kwargs)

    if self.path == '': # not loaded from database
      print("File not loaded from database")
      if kwargs.get('path', None) == None:
        self.path = str(self.generate_path())
        print("no path in kwargs, generating a path:" + self.path)

  def generate_path(self):
    return uuid.uuid4()

  def human_readable_size(self):
    return format_bytes(self.size, 2)


def format_bytes(size, precision):
    # 2**10 = 1024
    power = 2**10
    n = 0
    power_labels = {0 : '', 1: 'K', 2: 'M', 3: 'G', 4: 'T'}
    while size > power:
        size /= power
        n += 1
    size = round(size, precision)
    return "{} {}B".format(size, power_labels[n])

#class ContentType(models.Model):
#''' content-types, e.g. text/plain, text/html, x-application/binary-data '''
#  name = models.CharField(max_length=256)


#class FileExtension(models.Model):
#''' A filename extension and its associated content-type '''
#  type = models.ForeignKey(
#    'ContentType', on_delete = models.PROTECT)
#
#  extension = models.CharField(max_length=12)


#class FileVersion(models.Model):
#''' A version of a file. Keeps track of its oldest sibling file '''
#  file = models.OneToOneField(File)
#  oldest_sibling = models.OneToOneField(File)
#  version = models.IntegerField()


#class Checksum(models.Model):
#''' A type of checksum, e.g. SHA256, MD5 '''
#  type = models.CharField(max_length=12)


#class FileChecksum(models.Model):
#''' A checksum for a file '''
#  checksum = models.ForeignKey(
#    'Checksum', on_delete=models.PROTECT)
#
#  file = models.ForeignKey(
#    'File', on_delete=models.PROTECT)
#
#  value = models.CharField(max_length=256)


#class UploadProcessor(models.Model):
#''' File processors, e.g. Anti-virus scanner '''
#  type = models.CharField()
#
#
#class ProcessedFile(models.Model):
#  processor = scan:
#  file
#  date_processed
#  result
