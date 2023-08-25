from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.forms import modelformset_factory
from django.http import HttpResponseRedirect
from django.shortcuts import render, reverse
from django.template.context import RequestContext
from django.views.generic import FormView, TemplateView, ListView
from django.views.generic.base import TemplateResponseMixin
from enum import Enum
from datetime import date, datetime
from .forms import *
from .models import BillTo
from ..conf import settings


class DateInput(forms.DateInput):
  input_type = 'date'



class BillToIndexView(ListView):

  class ResponseDict(str, Enum):
    FORM = 'form'
    ITEMS = 'items'

  user = None
  template_name = settings.DEMOS_INVOICER_BILL_TO_LIST_TEMPLATE

  def setup(self, request, *args, **kwargs):
    super().setup(request, *args, **kwargs)

    if request.user.id:
      self.user = request.user
    else:
      self.user = None


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
  success_page = 'demos:invoicer:bill_to_view'
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

    print("print item")
    print(item.name)
    form = self.form_class(instance=item)

    self.response_dict[self.ResponseDict.FORM] = form

    print("before render")
    return render(request, self.template_name, self.response_dict)

  def post(self, request, *args, **kwargs):
    print("post")
    if request.POST.get('id'):
      item = BillTo.objects.get(owner=request.user, id=request.POST.get('id'))
    else:
      print("creating new BillTo")
      item = BillTo(owner=request.user)
    if item == None:
      print("Was None?")
    else:
      print("before print")
      print(item)

    form = self.form_class(instance=item, data=request.POST)

    print("form instance: {}".format(form.instance.name))
    if form.is_valid():
      print("the form is_valid")

      form.save()
      messages.info(request, "Bill-to was successfully updated.")
      query_string = "?id={}".format(form.instance.id)
      return HttpResponseRedirect(reverse(self.success_page) + query_string)
    else:
      print("not_valid()")

    query_string = "?id={}".format(form.instance.id)
    return HttpResponseRedirect(reverse(self.success_page) + query_string)

#    else:
#      return render(request, self.template_name, self.response_dict)


class InvoiceIndexView(ListView):

  class ResponseDict(str, Enum):
    FORM = 'form'
    ITEMS = 'items'

  user = None
  template_name = settings.DEMOS_INVOICER_INVOICE_LIST_TEMPLATE

  def setup(self, request, *args, **kwargs):
    super().setup(request, *args, **kwargs)

    if request.user.id:
      self.user = request.user
    else:
      self.user = None

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
    LINE_ITEMS = 'line_items'

  template_name = settings.DEMOS_INVOICER_INVOICE_TEMPLATE

  def __init__(self, *args, **kwargs):
    self.response_dict = {}

  def get(self, request, *args, **kwargs):
    id = request.GET.get('id')

    if id:
      try:
        if request.user and request.user.id:
          item = Invoice.objects.get(owner=request.user, id=id)
          line_items = LineItem.objects.filter(owner=request.user, invoice_id=id)
        else:
          print("No invoice: {}".format(id))
          item = Invoice.objects.get(owner=None, id=id)
          line_items = LineItem.objects.filter(owner=None, invoice_id=id)
        print(item)
        print(line_items)

      except Exception as e:
        print(str(e))
        messages.error(request, str(e))
        return render(request, self.template_name, self.response_dict)
    else:
      print("Shouldn't be here")
      item = Invoice(owner=request.user)

    self.response_dict[self.ResponseDict.ITEM] = item 
    self.response_dict[self.ResponseDict.LINE_ITEMS] = line_items

    return render(request, self.template_name, self.response_dict)


class InvoiceEditView(TemplateView):

  class ResponseDict(str, Enum):
    FORM = 'form'
    FORMSET = 'formset'
    INVOICE = 'invoice'
    LINE_ITEMS = 'line_items'

  form_class = InvoiceForm
  success_page = 'demos:invoicer:invoice_edit'
  view_page = 'demos:invoicer:invoice_view'
  template_name = settings.DEMOS_INVOICER_INVOICE_EDIT_TEMPLATE

  def __init__(self, *args, **kwargs):
    self.response_dict = {}

  def get(self, request, *args, **kwargs):
    print("{}.get()".format(self.__class__.__name__))
    id = request.GET.get('id')

    if id:
      try:
        if request.user and request.user.id:
          invoice = Invoice.objects.get(owner=request.user, id=id)
        else:
          invoice = Invoice.objects.get(owner=None, id=id)
      except Exception as e:
        print(str(e))
        messages.error(request, str(e))
        return render(request, self.template_name, self.response_dict)
    else:
      invoice = Invoice(owner=request.user)

    if invoice.status != 0:
      messages.error(request, "Can't modify, invoice status not 0.")
      query_string = "?id={}".format(id)
      return HttpResponseRedirect(reverse(self.view_page) + query_string)

    form = self.form_class(instance=invoice)

    self.response_dict[self.ResponseDict.FORM] = form
    self.response_dict[self.ResponseDict.INVOICE] = invoice

    formset = modelformset_factory(LineItem, form=LineItemForm, extra=3,exclude=['id','owner','invoice'],can_delete=True)
#    formset = modelformset_factory(LineItem, form=LineItemForm, extra=3,exclude=['id','owner','invoice'],can_delete=True,widgets={'status':forms.NumberInput(attrs={'max':0,'min':-1}),'date':DateInput(attrs={'max': date.today()}),'description':forms.Textarea(attrs={'cols':40,'rows':2}),'quantity':forms.NumberInput(attrs={'min':0.25,'step':0.25})})

#    self.response_dict[self.ResponseDict.FORMSET] = formset(queryset=LineItem.objects.filter(expense=invoice),initial=[{'date':date.today(),'invoice':invoice,'description':'initial description'}])
    self.response_dict[self.ResponseDict.FORMSET] = formset(queryset=LineItem.objects.filter(invoice=invoice),initial=[{'invoice':invoice,'description':''}])

    return render(request, self.template_name, self.response_dict)

  def post(self, request, *args, **kwargs):
#    if request.POST.get('id'):
#      item = Invoice.objects.get(owner=request.user, id=request.POST.get('id'))
#    else:
#      item = Invoice(owner=request.user)
   # form = self.form_class(instance=item, data=request.POST)

    invoice_id = request.POST.get('id',1) #FIX<E
    owner = request.user

    try:
      invoice = Invoice.objects.get(owner=owner, id=invoice_id)
    except Exception as e:
      invoice = Invoice(owner=owner)
      print("New invoice: {}".format(invoice.id))
#      return render(request, self.template_name, self.response_dict)

    if invoice.status != 0:
      messages.error(request, "Can't modify, invoice status not 0.")
      query_string = "?id={}".format(invoice_id)
      return HttpResponseRedirect(reverse(self.success_page) + query_string)

    invoice_form = self.form_class(instance=invoice, data=request.POST)

    if invoice_form.is_valid():
      try:
        invoice_form.save();
      except Exception as e:
        messages.error(request, "Couldn't save invoice: {}".format(e))
        return render(request, self.template_name, self.response_dict)

    else:
      print("invoice_form.errors: {}".format(invoice_form.errors))

    line_item_formset = modelformset_factory(
      LineItem,
      extra=3,
      exclude=['id','owner','invoice'],
      can_delete=True,
      widgets={
        'status':forms.NumberInput(attrs={'max':0,'min':-1}),
#        'date':DateInput(attrs={'max': date.today()}),
        'date':DateInput(attrs={}),
        'description':forms.Textarea(attrs={'cols':40,'rows':2}),
        'quantity':forms.NumberInput(attrs={'min':0.25,'step':0.25})
        }
      )

    print("POST: {}".format(request.POST))
#    formset = line_item_formset(request.POST,initial=[{'date':date.today(),'description':'initial description'}])
    formset = line_item_formset(request.POST,initial=[{}])
    #,queryset=LineItem.objects.filter(owner=request.user,invoice=invoice))

    if formset.is_valid():
      print("Formset: is_valid()")
      line_items = formset.save(commit=False)
      for line_item in line_items:
        line_item.invoice = invoice
        line_item.owner = owner
        print("Formset: save()")
        line_item.save()
      for line_item in formset.deleted_objects:
        print("Formset: delete()")
        line_item.delete()

      print("Formset: {} changed_objects, {} deleted_objects, {} new_objects".format(formset.changed_objects, formset.deleted_objects, formset.new_objects))
      if formset.changed_objects or formset.deleted_objects or formset.new_objects:
        messages.info(request, "Invoice updated: {} added, {} changed, {} deleted".format(len(formset.new_objects),len(formset.changed_objects),len(formset.deleted_objects)))
      else:
        messages.info(request, "No changes were made.")
      query_string = "?id={}".format(invoice_id)
      return HttpResponseRedirect(reverse(self.success_page) + query_string)
    else:
      print("Formset not valid")
      print(formset.errors)
      print("template_name: {}".format(self.template_name))
      messages.error(request, "Please fix the errors shown below.")

      self.response_dict[self.ResponseDict.FORM] = self.form_class(instance=invoice)
      self.response_dict[self.ResponseDict.INVOICE] = invoice
      self.response_dict[self.ResponseDict.FORMSET] = formset
      return render(request, self.template_name, self.response_dict)


class InvoiceRenderView(TemplateView):
  class ResponseDict(str, Enum):
    ITEM = 'invoice'
    LINE_ITEMS = 'line_items'

  template_name = settings.DEMOS_INVOICER_INVOICE_RENDER_TEMPLATE

  def __init__(self, *args, **kwargs):
    self.response_dict = {}

  def get(self, request, *args, **kwargs):
    id = request.GET.get('id')

    if id:
      try:
        if request.user and request.user.id:
          item = Invoice.objects.get(owner=request.user, id=id)
          line_items = LineItem.objects.filter(owner=request.user, invoice_id=id)
        else:
          item = Invoice.objects.get(owner=None, id=id)
        print(item)

      except Exception as e:
        print(str(e))
        messages.error(request, str(e))
        return render(request, self.template_name, self.response_dict)
    else:
      print("Shouldn't be here")
      items = []
      line_items = []

    self.response_dict[self.ResponseDict.ITEM] = item
    self.response_dict[self.ResponseDict.LINE_ITEMS] = line_items

    return render(request, self.template_name, self.response_dict)

