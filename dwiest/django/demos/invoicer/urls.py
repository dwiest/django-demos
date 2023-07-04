from django.urls import path
from .views import *
from django.views.generic import TemplateView

app_name = 'invoicer'

urlpatterns = [
  path('',
    TemplateView.as_view(
      template_name="dwiest-django-demos/invoicer/home.html"), name='home'),
  path('bill_to', BillToIndexView.as_view(), name='bill_to_index'),
  path('bill_to/edit', BillToEditView.as_view(), name='bill_to_edit'),
  path('bill_to/view', BillToView.as_view(), name='bill_to_view'),
  path('bill_to/add', BillToEditView.as_view(), name='bill_to_add'),
  path('invoice', InvoiceIndexView.as_view(), name='invoice_index'),
  path('invoice/edit', InvoiceEditView.as_view(), name='invoice_edit'),
  path('invoice/view', InvoiceView.as_view(), name='invoice_view'),
  path('invoice/add', InvoiceEditView.as_view(), name='invoice_add'),
]
