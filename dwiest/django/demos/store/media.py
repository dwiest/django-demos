"""Product images live in S3; Django stores only their object location and metadata."""
import logging
import re
from io import BytesIO
from uuid import uuid4
import warnings
from urllib.parse import quote, urlsplit
from django.core.exceptions import ImproperlyConfigured

import boto3
from botocore.config import Config
from django.conf import settings
from django.core.exceptions import ValidationError
from PIL import Image, ImageOps, UnidentifiedImageError

logger = logging.getLogger(__name__)
MAX_BYTES = 10 * 1024 * 1024
MAX_PIXELS = 24_000_000
MAX_BATCH = 10
FORMATS = {'JPEG': ('jpg', 'image/jpeg'), 'PNG': ('png', 'image/png'), 'WEBP': ('webp', 'image/webp')}


def s3_client():
    # Path addressing supports HTTPS for dotted names such as rotten.world.
    return boto3.client('s3', region_name=getattr(settings, 'STORE_MEDIA_REGION', None),
                        config=Config(signature_version='s3v4', s3={'addressing_style': 'path'},
                                      connect_timeout=5, read_timeout=30,
                                      retries={'max_attempts': 2, 'mode': 'standard'}))


def prepare_image(upload):
    """Decode and re-encode allowlisted raster images; discard client MIME and metadata."""
    if upload.size > MAX_BYTES:
        raise ValidationError('Each photo must be 10 MB or smaller.')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(upload, formats=list(FORMATS)) as image:
                if image.width * image.height > MAX_PIXELS:
                    raise ValidationError('Each photo must contain at most 24 million pixels.')
                if getattr(image, 'is_animated', False):
                    raise ValidationError('Upload a still image, rather than an animation.')
                image_format = image.format
                image.load()
                normalized = ImageOps.exif_transpose(image)
                if image_format == 'JPEG':
                    normalized = normalized.convert('RGB')
                elif normalized.mode not in ('RGB', 'RGBA'):
                    normalized = normalized.convert('RGBA')
                normalized.info.clear()
                output = BytesIO()
                normalized.save(output, format=image_format)
                data = output.getvalue()
                width, height = normalized.size
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError,
            Image.DecompressionBombWarning, Image.DecompressionBombError):
        raise ValidationError('Upload a valid JPEG, PNG, or WebP photo.')
    finally:
        upload.seek(0)
    if len(data) > MAX_BYTES:
        raise ValidationError('The processed photo exceeds 10 MB. Please resize it.')
    extension, content_type = FORMATS[image_format]
    return {'data': data, 'extension': extension, 'content_type': content_type,
            'width': width, 'height': height}


def prepare_thank_you_image(upload):
    """Validate a GIF and preserve its original bytes so animation survives."""
    if upload.size > MAX_BYTES:
        raise ValidationError('The thank-you image must be 10 MB or smaller.')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(upload, formats=['GIF']) as image:
                width, height = image.size
                if width * height > MAX_PIXELS:
                    raise ValidationError('The thank-you image must contain at most 24 million pixels.')
                image.verify()
        upload.seek(0)
        data = upload.read()
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError,
            Image.DecompressionBombWarning, Image.DecompressionBombError):
        raise ValidationError('Upload a valid GIF image for the thank-you page.')
    finally:
        upload.seek(0)
    if len(data) > MAX_BYTES:
        raise ValidationError('The thank-you image must be 10 MB or smaller.')
    return {'data': data, 'extension': 'gif', 'content_type': 'image/gif',
            'width': width, 'height': height}


def upload_asset(directory, prepared):
    bucket = getattr(settings, 'STORE_MEDIA_BUCKET', 'rotten.world')
    prefix = getattr(settings, 'STORE_MEDIA_PREFIX', 'store/products').strip('/')
    key = '{}/{}/{}.{}'.format(prefix, directory, uuid4().hex, prepared['extension'])
    s3_client().put_object(Bucket=bucket, Key=key, Body=prepared['data'],
                           ContentType=prepared['content_type'], CacheControl='private, max-age=300')
    return bucket, key



def upload_image(product, prepared):
    return upload_asset(str(product.pk), prepared)


def permanent_url(bucket, key):
    """Never place expiring S3 signatures in email. Empty means omit artwork."""
    base = getattr(settings, 'STORE_MEDIA_PUBLIC_BASE_URL', '').rstrip('/')
    if not base or not key:
        return ''
    parsed = urlsplit(base)
    if parsed.scheme != 'https' or not parsed.netloc or parsed.query or parsed.fragment or parsed.username:
        raise ImproperlyConfigured('STORE_MEDIA_PUBLIC_BASE_URL must be a permanent HTTPS base URL.')
    if bucket != getattr(settings, 'STORE_MEDIA_BUCKET', 'rotten.world'):
        return ''
    # A direct S3 endpoint always maps a complete stored key from the bucket
    # root. UI/media folders in its configured path are not S3 key prefixes.
    host = parsed.hostname or ''
    endpoint = host[len(bucket) + 1:] if host.startswith(bucket + '.') else host
    if re.fullmatch(r's3(?:[.-][a-z0-9-]+)?\.amazonaws\.com', endpoint):
        base = 'https://{}/{}'.format(endpoint, quote(bucket, safe=''))
    return base + '/' + quote(key, safe='/')


def photo_url(photo):
    # Storefront and branding retain authenticated S3 delivery. The public base
    # setting is exclusively for email; it must never redirect existing images.
    return s3_client().generate_presigned_url(
        'get_object', Params={'Bucket': photo.bucket, 'Key': photo.key},
        ExpiresIn=getattr(settings, 'STORE_MEDIA_URL_TTL', 3600))


def delete_image(bucket, key):
    """Best effort cleanup after a DB commit; failures retain the object, not a broken row."""
    try:
        s3_client().delete_object(Bucket=bucket, Key=key)
    except Exception:
        logger.exception('Unable to remove store image s3://%s/%s', bucket, key)


def record_photo_version(photo):
    from .models import ProductPhotoVersion
    ProductPhotoVersion.objects.get_or_create(photo=photo, version=photo.version, defaults={
        'bucket': photo.bucket, 'key': photo.key, 'width': photo.width, 'height': photo.height})


def snapshot_image(variant):
    # Prefer this option's photo, then a generic product photo. Never use another option's photo.
    photos = list(variant.product.photos.all())
    photo = next((p for p in photos if p.variant_id == variant.pk), None)
    photo = photo or next((p for p in photos if p.variant_id is None), None)
    if not photo:
        return {}
    return {'image_bucket': photo.bucket, 'image_key': photo.key,
            'image_alt': photo.alt_text or variant.product.name}
