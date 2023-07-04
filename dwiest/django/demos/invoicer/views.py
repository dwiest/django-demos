from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.http import HttpResponseRedirect
from django.shortcuts import render, reverse
from django.template.context import RequestContext
from django.views.generic import FormView, TemplateView, ListView
from django.views.generic.base import TemplateResponseMixin
from enum import Enum
from datetime import datetime
from .forms import *
from .models import BillTo
from ..conf import settings


class BillToIndexView(ListView):

  class ResponseDict(str, Enum):
    FORM = 'form'
    ITEMS = 'items'

  user = None
  template_name = settings.DEMOS_INVOICER_BILL_TO_LIST_TEMPLATE

  def get_template_names(self):
    return [self.template_name]

  def get_queryset(self):
    if self.user:
      owner_q = Q(owner=self.user)
    else:
      owner_q = Q(owner=None)

    items = BillTo.objects.filter(owner_q)

    return items 

  def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
#    if self.url:
#      context[self.ResponseDict.FORM] = self.form_class(data={'url':self.url})
#    else:
#      context[self.ResponseDict.FORM] = self.form_class()
    context[self.ResponseDict.ITEMS] = self.get_queryset()

    return context


class BillToView(TemplateView):

  class ResponseDict(str, Enum):
    ITEM = 'bill_to'

  template_name = settings.DEMOS_INVOICER_BILL_TO_TEMPLATE

  def __init__(self, *args, **kwargs):
    self.response_dict = {}

  def get(self, request, *args, **kwargs):
    id = request.GET.get('id')

    if id:
      try:
        if request.user and request.user.id:
          item = BillTo.objects.get(owner=request.user, id=id, status=0)
        else:
          item = BillTo.objects.get(owner=None, id=id, status=0)
        print(item)

      except Exception as e:
        print(str(e))
        messages.error(request, str(e))
        return render(request, self.template_name, self.response_dict)
    else:
      print("Shouldn't be here")
      item = BillTo(owner=request.user)

    self.response_dict[self.ResponseDict.ITEM] = item 

    return render(request, self.template_name, self.response_dict)


class BillToEditView(TemplateView):

  class ResponseDict(str, Enum):
    FORM = 'form'

  form_class = BillToForm
  success_page = 'demos:invoicer:billto_view'
  template_name = settings.DEMOS_INVOICER_BILL_TO_EDIT_TEMPLATE

  def __init__(self, *args, **kwargs):
    self.response_dict = {}

  def get(self, request, *args, **kwargs):
    print("{}.get()".format(self.__class__.__name__))
    id = request.GET.get('id')

    if id:
      try:
        if request.user and request.user.id:
          item = BillTo.objects.get(owner=request.user, id=id)
        else:
          item = BillTo.objects.get(owner=None, id=id)
      except Exception as e:
        print(str(e))
        messages.error(request, str(e))
        return render(request, self.template_name, self.response_dict)
    else:
      item = BillTo(owner=request.user)

    form = self.form_class(instance=item)

    self.response_dict[self.ResponseDict.FORM] = form

    return render(request, self.template_name, self.response_dict)

  def post(self, request, *args, **kwargs):
    if request.POST.get('id'):
      item = BillTo.objects.get(owner=request.user, id=request.POST.get('id'))
    else:
      item = BillTo(owner=request.user)
    form = self.form_class(instance=item, data=request.POST)

    if form.is_valid():
      print("is_valid()")
      form.save()
      messages.info(request, "Bill-to was successfully updated.")
      query_string = "?id={}".format(form.instance.id)
      return HttpResponseRedirect(reverse(self.success_page) + query_string)
    else:
      print("not_valid()")

### HERE

class InvoiceIndexView(ListView):

  class ResponseDict(str, Enum):
    FORM = 'form'
    ITEMS = 'items'

  user = None
  template_name = settings.DEMOS_INVOICER_INVOICE_LIST_TEMPLATE

  def get_template_names(self):
    return [self.template_name]

  def get_queryset(self):
    if self.user:
      owner_q = Q(owner=self.user)
    else:
      owner_q = Q(owner=None)

    items = Invoice.objects.filter(owner_q)

    return items 

  def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
#    if self.url:
#      context[self.ResponseDict.FORM] = self.form_class(data={'url':self.url})
#    else:
#      context[self.ResponseDict.FORM] = self.form_class()
    context[self.ResponseDict.ITEMS] = self.get_queryset()

    return context


class InvoiceView(TemplateView):

  class ResponseDict(str, Enum):
    ITEM = 'invoice'

  template_name = settings.DEMOS_INVOICER_INVOICE_TEMPLATE

  def __init__(self, *args, **kwargs):
    self.response_dict = {}

  def get(self, request, *args, **kwargs):
    id = request.GET.get('id')

    if id:
      try:
        if request.user and request.user.id:
          item = Invoice.objects.get(owner=request.user, id=id, status=0)
        else:
          item = Invoice.objects.get(owner=None, id=id, status=0)
        print(item)

      except Exception as e:
        print(str(e))
        messages.error(request, str(e))
        return render(request, self.template_name, self.response_dict)
    else:
      print("Shouldn't be here")
      item = Invoice(owner=request.user)

    self.response_dict[self.ResponseDict.ITEM] = item 

    return render(request, self.template_name, self.response_dict)


class InvoiceEditView(TemplateView):

  class ResponseDict(str, Enum):
    FORM = 'form'

  form_class = InvoiceForm
  success_page = 'demos:invoicer:invoice_view'
  template_name = settings.DEMOS_INVOICER_INVOICE_EDIT_TEMPLATE

  def __init__(self, *args, **kwargs):
    self.response_dict = {}

  def get(self, request, *args, **kwargs):
    print("{}.get()".format(self.__class__.__name__))
    id = request.GET.get('id')

    if id:
      try:
        if request.user and request.user.id:
          item = Invoice.objects.get(owner=request.user, id=id)
        else:
          item = Invoice.objects.get(owner=None, id=id)
      except Exception as e:
        print(str(e))
        messages.error(request, str(e))
        return render(request, self.template_name, self.response_dict)
    else:
      item = Invoice(owner=request.user)

    form = self.form_class(instance=item)

    self.response_dict[self.ResponseDict.FORM] = form

    return render(request, self.template_name, self.response_dict)

  def post(self, request, *args, **kwargs):
    if request.POST.get('id'):
      item = Invoice.objects.get(owner=request.user, id=request.POST.get('id'))
    else:
      item = Invoice(owner=request.user)
    form = self.form_class(instance=item, data=request.POST)

    if form.is_valid():
      print("is_valid()")
      form.save()
      messages.info(request, "Invoice was successfully updated.")
      query_string = "?id={}".format(form.instance.id)
      return HttpResponseRedirect(reverse(self.success_page) + query_string)
    else:
      print("not_valid()")
