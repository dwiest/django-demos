from django.urls import path
from .views import *

app_name = 'bookmarks'

urlpatterns = [
  path('',
    BookmarksView.as_view(), name='home'),
  path('add',
    QuickAddBookmarkView.as_view(), name='add'),
  path('bookmark',
    BookmarkView.as_view(), name='bookmark'),
  path('export',
    BookmarkExportView.as_view(), name='export'),
]
