"""Escaped JSON presentation shared by saved job and provenance views."""
import json
import uuid
from django import template

register = template.Library()


@register.inclusion_tag('dwiest-django-demos/bookmarks/components/json_value.html', takes_context=True)
def json_value(context, value):
    return {'user': context.get('user'), 'json_id': 'json-' + uuid.uuid4().hex,
            'raw': json.dumps(value, ensure_ascii=False, separators=(',', ':'), default=str),
            'pretty': json.dumps(value, ensure_ascii=False, indent=2, default=str)}


MONTH_ICONS = {1: '❄️', 2: '❤️', 3: '☘️', 4: '🌷', 5: '🌼', 6: '☀️',
               7: '🇺🇸', 8: '🌻', 9: '🍂', 10: '🎃', 11: '🦃', 12: '🎄 🎁'}


@register.inclusion_tag('dwiest-django-demos/bookmarks/components/month_header.html')
def month_header(value):
    from django.conf import settings
    from urllib.parse import urlsplit
    month = value.month if value else None
    headers = getattr(settings, 'BOOKMARKS_MONTH_HEADERS', {})
    config = headers.get(month, headers.get(str(month), {})) if isinstance(headers, dict) else {}
    config = config if isinstance(config, dict) else {}
    image = config.get('image_url', '')
    try:
        parsed = urlsplit(image)
        safe = isinstance(image, str) and not any(ord(c) < 32 or c == '\\' for c in image) and (
            (image.startswith('/') and not image.startswith('//')) or
            (parsed.scheme == 'https' and parsed.hostname and not parsed.username and not parsed.password))
    except (ValueError, TypeError):
        safe = False
    return {'date': value, 'month': month or '', 'icon': config.get('icon', MONTH_ICONS.get(month, '🔖')),
            'image_url': image if safe else ''}
