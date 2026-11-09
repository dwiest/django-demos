from django.db import transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver

from .media import delete_image
from .models import ProductPhoto, StoreBranding


@receiver(post_delete, sender=ProductPhoto)
def delete_photo_object(sender, instance, **kwargs):
    bucket, key = instance.bucket, instance.key
    transaction.on_commit(lambda: delete_image(bucket, key))


@receiver(post_delete, sender=StoreBranding)
def delete_branding_objects(sender, instance, **kwargs):
    for location in ('header', 'footer'):
        bucket = getattr(instance, location + '_image_bucket')
        key = getattr(instance, location + '_image_key')
        if key:
            transaction.on_commit(lambda bucket=bucket, key=key: delete_image(bucket, key))
