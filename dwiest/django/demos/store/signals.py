from django.db import transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver

from .media import delete_image
from .models import ProductPhoto


@receiver(post_delete, sender=ProductPhoto)
def delete_photo_object(sender, instance, **kwargs):
    bucket, key = instance.bucket, instance.key
    transaction.on_commit(lambda: delete_image(bucket, key))
