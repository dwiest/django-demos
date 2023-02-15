from django.dispatch import receiver
from django.dispatch import Signal

file_deleted = Signal()
file_updated = Signal()
file_uploaded = Signal()

@receiver(file_deleted)
def deleted(sender, **kwargs):
  print("File was deleted: id={}, name={}".format(kwargs.get('id'),kwargs.get('name')))

@receiver(file_updated)
def updated(sender, **kwargs):
  print("File was updated: id={}, name={}".format(kwargs.get('id'),kwargs.get('name')))

@receiver(file_uploaded)
def uploaded(sender, **kwargs):
  print("File was uploaded: id={}, name={}".format(kwargs.get('id'),kwargs.get('name')))
