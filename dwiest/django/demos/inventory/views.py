from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Q
#from django.forms import modelformset_factory
from django.http import HttpResponseRedirect
from django.shortcuts import render, reverse
from django.template.context import RequestContext
from django.views.generic import FormView, TemplateView, ListView
from django.views.generic.base import TemplateResponseMixin
from enum import Enum
from datetime import date, datetime
from .forms import InventoryListForm, InventoryItemForm, InventoryEntryForm
from .models import InventoryList, InventoryItem, InventoryEntry
from ..conf import settings


#class DateInput(forms.DateInput):
#  input_type = 'date'


class InventoryListHomeView(ListView):

  class ResponseDict(str, Enum):
    ITEMS = 'items'
    LISTS = 'lists'

  user = None
  template_name = settings.DEMOS_INVENTORY_LIST_HOME_TEMPLATE

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

    lists = InventoryList.objects.filter(owner_q)
    #lists = InventoryList.objects.all()

    return lists

  def get_items_queryset(self):
    if self.user:
      owner_q = Q(owner=self.user)
    else:
      owner_q = Q(owner=None)

    items = InventoryItem.objects.filter(owner_q)

    return items 

  def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
#    if self.url:
#      context[self.ResponseDict.FORM] = self.form_class(data={'url':self.url})
#    else:
#      context[self.ResponseDict.FORM] = self.form_class()
    context[self.ResponseDict.LISTS] = self.get_queryset()
    context[self.ResponseDict.ITEMS] = self.get_items_queryset()

    return context


class InventoryListView(ListView):

  class ResponseDict(str, Enum):
    ITEMS = 'items'
    LIST = 'list'

  user = None
  template_name = settings.DEMOS_INVENTORY_LIST_VIEW_TEMPLATE

  def setup(self, request, *args, **kwargs):
    super().setup(request, *args, **kwargs)

    if request.user.id:
      self.user = request.user
    else:
      self.user = None

    self.list_id = request.GET.get('id')

  def get_template_names(self):
    return [self.template_name]

  def get_queryset(self):
    if self.user:
      owner_q = Q(owner=self.user)
    else:
      owner_q = Q(owner=None)

    if self.list_id:
      list = InventoryList.objects.get(owner_q, id=self.list_id)
    else:
      list = None

    return list

  def get_item_queryset(self):
    if self.user:
      owner_q = Q(owner=self.user)
    else:
      owner_q = Q(owner=None)

    items = InventoryEntry.objects.filter(owner_q, inventory_list_id=self.list_id)
    print(items)

    return items


  def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
#    if self.url:
#      context[self.ResponseDict.FORM] = self.form_class(data={'url':self.url})
#    else:
#      context[self.ResponseDict.FORM] = self.form_class()
    context[self.ResponseDict.LIST] = self.get_queryset()
    context[self.ResponseDict.ITEMS] = self.get_item_queryset()

    return context


class InventoryListEditView(TemplateView):

  class ResponseDict(str, Enum):
    FORM = 'form'

  form_class = InventoryListForm
  success_page = 'demos:inventory:list_view'
  delete_page = 'demos:inventory:home'
  template_name = settings.DEMOS_INVENTORY_LIST_EDIT_TEMPLATE

  def __init__(self, *args, **kwargs):
    self.response_dict = {}

  def get(self, request, *args, **kwargs):
    print("{}.get()".format(self.__class__.__name__))
    id = request.GET.get('id')

    if id:
      try:
        if request.user and request.user.id:
          item = InventoryList.objects.get(owner=request.user, id=id)
        else:
          item = InventoryList.objects.get(owner=None, id=id)
      except Exception as e:
        print(str(e))
        messages.error(request, str(e))
        return render(request, self.template_name, self.response_dict)
    else:
      item = InventoryList(owner=request.user)

    print("print item")
    print(item.name)
    form = self.form_class(instance=item)

    self.response_dict[self.ResponseDict.FORM] = form

    print("before render")
    return render(request, self.template_name, self.response_dict)

  def post(self, request, *args, **kwargs):
    if request.POST.get('id'):
      item = InventoryList.objects.get(owner=request.user, id=request.POST.get('id'))
    else:
      item = InventoryList(owner=request.user)
    if item == None:
      print("Was None?")

    form = self.form_class(instance=item, data=request.POST)

    delete_list = request.POST.get('delete')

    if form.is_valid():
      try:
        if delete_list:
          print("DELETE LIST")
          form.instance.delete()
        else:
          form.save();
      except Exception as e:
        messages.error(request, "Couldn't save InventoryList: {}".format(e))
        print("rendering")
        self.response_dict[self.ResponseDict.FORM] = form
        return render(request, self.template_name, self.response_dict)

    query_string = "?id={}".format(item.id)

    print("redirecting")
    if delete_list:
      return HttpResponseRedirect(reverse(self.delete_page))
    else:
      return HttpResponseRedirect(reverse(self.success_page) + query_string)
    #return render(request, self.template_name, self.response_dict)


class InventoryItemView(ListView):

  class ResponseDict(str, Enum):
    ITEM = 'item'

  user = None
  template_name = settings.DEMOS_INVENTORY_ITEM_VIEW_TEMPLATE

  def setup(self, request, *args, **kwargs):
    super().setup(request, *args, **kwargs)

    if request.user.id:
      self.user = request.user
    else:
      self.user = None

    self.item_id = request.GET.get('id')

  def get_template_names(self):
    return [self.template_name]

  def get_queryset(self):
    if self.user:
      owner_q = Q(owner=self.user)
    else:
      owner_q = Q(owner=None)

    if self.item_id:
      item = InventoryItem.objects.get(owner_q, id=self.item_id)
    else:
      item = None

    return item


  def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    context[self.ResponseDict.ITEM] = self.get_queryset()

    return context


class InventoryItemEditView(TemplateView):

  class ResponseDict(str, Enum):
    FORM = 'form'

  form_class = InventoryItemForm
  success_page = 'demos:inventory:home'
  delete_page = 'demos:inventory:home'
  template_name = settings.DEMOS_INVENTORY_ITEM_EDIT_TEMPLATE

  def __init__(self, *args, **kwargs):
    self.response_dict = {}

  def get(self, request, *args, **kwargs):
    print("{}.get()".format(self.__class__.__name__))
    id = request.GET.get('id')

    if id:
      try:
        if request.user and request.user.id:
          item = InventoryItem.objects.get(owner=request.user, id=id)
        else:
          item = InventoryItem.objects.get(owner=None, id=id)
      except Exception as e:
        print(str(e))
        messages.error(request, str(e))
        return render(request, self.template_name, self.response_dict)
    else:
      item = InventoryItem(owner=request.user)

    print("print item")
    print(item.name)
    form = self.form_class(instance=item)

    self.response_dict[self.ResponseDict.FORM] = form

    print("before render")
    return render(request, self.template_name, self.response_dict)

  def post(self, request, *args, **kwargs):
    if request.POST.get('id'):
      item = InventoryItem.objects.get(owner=request.user, id=request.POST.get('id'))
    else:
      item = InventoryItem(owner=request.user)
    if item == None:
      print("Was None?")

    form = self.form_class(instance=item, data=request.POST)

    delete_item = request.POST.get('delete')

    if form.is_valid():
      try:
        if delete_item:
          print("DELETE!")
          form.instance.delete()
        else:
          form.save();
      except Exception as e:
        messages.error(request, "Couldn't save InventoryItem: {}".format(e))
        print("rendering")
        self.response_dict[self.ResponseDict.FORM] = form
        return render(request, self.template_name, self.response_dict)

    print("redirecting")
    if delete_item:
      return HttpResponseRedirect(reverse(self.delete_page))
    else:
      return HttpResponseRedirect(reverse(self.success_page))
    #return render(request, self.template_name, self.response_dict)

class InventoryEntryView(ListView):

  class ResponseDict(str, Enum):
    ITEM = 'item'

  user = None
  template_name = settings.DEMOS_INVENTORY_ENTRY_VIEW_TEMPLATE

  def setup(self, request, *args, **kwargs):
    super().setup(request, *args, **kwargs)

    if request.user.id:
      self.user = request.user
    else:
      self.user = None

    self.item_id = request.GET.get('id')

  def get_template_names(self):
    return [self.template_name]

  def get_queryset(self):
    if self.user:
      owner_q = Q(owner=self.user)
    else:
      owner_q = Q(owner=None)

    if self.item_id:
      item = InventoryEntry.objects.get(owner_q, id=self.item_id)
    else:
      item = None

    return item


  def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    context[self.ResponseDict.ITEM] = self.get_queryset()

    return context


class InventoryEntryEditView(TemplateView):

  class ResponseDict(str, Enum):
    FORM = 'form'

  form_class = InventoryEntryForm
  success_page = 'demos:inventory:list_view'
  delete_page = 'demos:inventory:list_view'
  template_name = settings.DEMOS_INVENTORY_ENTRY_EDIT_TEMPLATE

  def __init__(self, *args, **kwargs):
    self.response_dict = {}

  def get(self, request, *args, **kwargs):
    print("{}.get()".format(self.__class__.__name__))
    id = request.GET.get('id')
    list_id = request.GET.get('list')

    if id:
      try:
        if request.user and request.user.id:
          item = InventoryEntry.objects.get(owner=request.user, id=id)
        else:
          item = InventoryEntry.objects.get(owner=None, id=id)
      except Exception as e:
        print(str(e))
        messages.error(request, str(e))
        return render(request, self.template_name, self.response_dict)
    else:
      item = InventoryEntry(owner=request.user, inventory_list_id=list_id)

    print("print item")
    print(item.id)
    form = self.form_class(instance=item)

    self.response_dict[self.ResponseDict.FORM] = form

    print("before render")
    return render(request, self.template_name, self.response_dict)

  def post(self, request, *args, **kwargs):
    if request.POST.get('id'):
      item = InventoryEntry.objects.get(owner=request.user, id=request.POST.get('id'))
    else:
      item = InventoryEntry(owner=request.user)
    if item == None:
      print("Was None?")

    form = self.form_class(instance=item, data=request.POST)

    delete_entry = request.POST.get('delete')

    if form.is_valid():
      try:
        if delete_entry:
          print("DELETE entry")
          form.instance.delete()
        else:
          form.save();
      except Exception as e:
        messages.error(request, "Couldn't save InventoryEntry: {}".format(e))
        print("rendering")
        self.response_dict[self.ResponseDict.FORM] = form
        return render(request, self.template_name, self.response_dict)

    query_string = "?id={}".format(item.inventory_list_id)

    print("redirecting")
    if delete_entry:
      return HttpResponseRedirect(reverse(self.delete_page) + query_string)
    else:
      return HttpResponseRedirect(reverse(self.success_page) + query_string)
