from django import template
from ..application_access import navigation

register = template.Library()


@register.simple_tag(takes_context=True)
def application_catalog(context, services=False):
    return navigation(context.get('request'), services=services)
