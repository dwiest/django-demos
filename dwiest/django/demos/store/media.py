"""Product images live in S3; Django stores only their object location and metadata."""
import logging
from io import BytesIO
from uuid import uuid4
import warnings

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


def upload_asset(directory, prepared):
    bucket = getattr(settings, 'STORE_MEDIA_BUCKET', 'rotten.world')
    prefix = getattr(settings, 'STORE_MEDIA_PREFIX', 'store/products').strip('/')
    key = '{}/{}/{}.{}'.format(prefix, directory, uuid4().hex, prepared['extension'])
    s3_client().put_object(Bucket=bucket, Key=key, Body=prepared['data'],
                           ContentType=prepared['content_type'], CacheControl='private, max-age=300')
    return bucket, key



def upload_image(product, prepared):
    return upload_asset(str(product.pk), prepared)


def photo_url(photo):
    return s3_client().generate_presigned_url(
        'get_object', Params={'Bucket': photo.bucket, 'Key': photo.key},
        ExpiresIn=getattr(settings, 'STORE_MEDIA_URL_TTL', 3600))


def delete_image(bucket, key):
    """Best effort cleanup after a DB commit; failures retain the object, not a broken row."""
    try:
        s3_client().delete_object(Bucket=bucket, Key=key)
    except Exception:
        logger.exception('Unable to remove store image s3://%s/%s', bucket, key)
