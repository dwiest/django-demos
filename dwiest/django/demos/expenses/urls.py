from django.urls import path
from .views import *
from django.views.generic import TemplateView

app_name = 'expenses'

urlpatterns = [
#  path('',
#    TemplateView.as_view(
#      template_name="dwiest-django-demos/expenses/home.html"), name='home'),
  path('', ExpenseListIndexView.as_view(), name='home'),
  path('list/view', ExpenseListView.as_view(), name='list_view'),
  path('list/add', ExpenseListEditView.as_view(), name='list_add'),
  path('list/edit', ExpenseListEditView.as_view(), name='list_edit'),
  path('category/view', ExpenseCategoryView.as_view(), name='category_view'),
  path('category/edit', ExpenseCategoryEditView.as_view(), name='category_edit'),
  path('category/add', ExpenseCategoryEditView.as_view(), name='category_add'),
]
