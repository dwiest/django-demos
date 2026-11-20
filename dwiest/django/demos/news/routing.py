#from .wsgi import *
from django.urls import re_path

from .consumers import *

websocket_demos_news= [
    re_path(r"apps/ws/demos/news/", NewsFeed.as_asgi()),
]
