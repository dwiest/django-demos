from django.templatetags.static import static
from django.urls import reverse
from django.template.defaulttags import ifchanged
from django.template.base import Parser, Token, TokenType

from jinja2 import Environment

def environment(**options):
    print("woohoo")
    env = Environment(**options)
    env.globals.update(
        {
            'static':static,
            'url':reverse,
            'ifchanged':ifchanged,
            'Parser':Parser,
            'Token':Token,
            'TokenType':TokenType,
        }
    )
    
    return env
