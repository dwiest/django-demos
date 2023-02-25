from django.urls import path
from .views import BookmarksView, AddBookmarkView

app_name = 'bookmarks'

urlpatterns = [
  path('',
    BookmarksView.as_view(), name='home'),
  path('add',
    AddBookmarkView.as_view(), name='add'),
]
