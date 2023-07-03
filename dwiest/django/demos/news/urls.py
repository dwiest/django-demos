from django.urls import path
from .views import *

app_name = 'news'

urlpatterns = [
  path('',
    NewsItemListView.as_view(), name='home'),
  path('view',
    NewsItemView.as_view(), name='view'),
  path('create',
    NewsItemEditView.as_view(), name='create'),
  path('edit',
    NewsItemEditView.as_view(), name='edit'),
  path('delete',
    DeleteView.as_view(), name='delete'),
#  path('entry',
#    JournalEntryView.as_view(), name='entry'),
#  path('entry/edit',
#    JournalEntryEditView.as_view(), name='entry_edit'),
]
