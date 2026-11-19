import math
from django import template

register = template.Library()


@register.filter
def elapsed(value):
    try:
        number = float(value)
        if not math.isfinite(number):
            return 'Unavailable'
        total = max(0, int(number))
    except (TypeError, ValueError, OverflowError):
        return 'Unavailable'
    hours, rest = divmod(total, 3600)
    minutes, seconds = divmod(rest, 60)
    parts = []
    if hours:
        parts.append('{} hour{}'.format(hours, '' if hours == 1 else 's'))
    if minutes or hours:
        parts.append('{} minute{}'.format(minutes, '' if minutes == 1 else 's'))
    parts.append('{} second{}'.format(seconds, '' if seconds == 1 else 's'))
    return ', '.join(parts)
