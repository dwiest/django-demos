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
  path('tags',
    TagsView.as_view(), name='tags'),
  path('tags/edit',
    TagFormView.as_view(), name='tag_edit'),
  path('tags/create',
    TagFormView.as_view(), name='tag_create'),
  path('tags/view',
    TagView.as_view(), name='tag_view'),
  path('tag',
    BookmarkTagFormView.as_view(), name='tag'),
]
