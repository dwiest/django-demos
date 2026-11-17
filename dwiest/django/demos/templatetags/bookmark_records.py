"""Escaped JSON presentation shared by saved job and provenance views."""
import json
import uuid
from django import template

register = template.Library()


@register.inclusion_tag('dwiest-django-demos/bookmarks/components/json_value.html')
def json_value(value):
    return {'json_id': 'json-' + uuid.uuid4().hex,
            'raw': json.dumps(value, ensure_ascii=False, separators=(',', ':'), default=str),
            'pretty': json.dumps(value, ensure_ascii=False, indent=2, default=str)}
