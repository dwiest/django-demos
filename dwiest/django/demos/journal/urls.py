from django.urls import path
from .views import *

app_name = 'journal'

urlpatterns = [
  path('',
    JournalListView.as_view(), name='home'),
  path('view',
    JournalView.as_view(), name='view'),
  path('create',
    JournalEditView.as_view(), name='create'),
  path('edit',
    JournalEditView.as_view(), name='edit'),
  path('entry',
    JournalEntryView.as_view(), name='entry'),
  path('entry/edit',
    JournalEntryEditView.as_view(), name='entry_edit'),
]
