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
from .models import *
from ..conf import settings


class DateInput(forms.DateInput):
  input_type = 'date'



class ExpenseListIndexView(ListView):

  class ResponseDict(str, Enum):
    LISTS = 'expense_lists'
    CATEGORIES = 'expense_categories'

  user = None
  template_name = settings.DEMOS_EXPENSES_EXPENSE_TEMPLATE

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
    return ExpenseList.objects.filter(owner_q)

  def get_categories(self):
    if self.user:
      owner_q = Q(owner=self.user)
    else:
      owner_q = Q(owner=None)
    return ExpenseCategory.objects.filter(owner_q)

  def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
#    if self.url:
#      context[self.ResponseDict.FORM] = self.form_class(data={'url':self.url})
#    else:
#      context[self.ResponseDict.FORM] = self.form_class()
    context[self.ResponseDict.LISTS] = self.get_queryset()
    context[self.ResponseDict.CATEGORIES] = self.get_categories()

    return context



class ExpenseCategoryView(TemplateView):
  template_name = settings.DEMOS_EXPENSES_EXPENSE_CATEGORY_TEMPLATE

  class ResponseDict(str, Enum):
    CATEGORY = 'expense_category'

  def __init__(self, *args, **kwargs):
    self.response_dict = {}

  def get(self, request, *args, **kwargs):
    print("{}.get()".format(self.__class__.__name__))
    id = request.GET.get('id')

    if id:
      try:
        if request.user and request.user.id:
          expense_category = ExpenseCategory.objects.get(owner=request.user, id=id)
        else:
          expense_category = ExpenseCategory.objects.get(owner=None, id=id)
      except Exception as e:
        print(str(e))
        messages.error(request, str(e))
        return render(request, self.template_name, self.response_dict)
    else:
      expense_category = None

    self.response_dict[self.ResponseDict.CATEGORY] = expense_category

    return render(request, self.template_name, self.response_dict)


class ExpenseCategoryEditView(TemplateView):
  class ResponseDict(str, Enum):
    FORM = 'form'
    CATEGORY = 'expense_category'

  form_class = ExpenseCategoryForm
  template_name = settings.DEMOS_EXPENSES_EXPENSE_CATEGORY_EDIT_TEMPLATE
  success_page = "demos:expenses:category_view"

  def __init__(self, *args, **kwargs):
    self.response_dict = {}

  def get(self, request, *args, **kwargs):
    print("{}.get()".format(self.__class__.__name__))
    id = request.GET.get('id')

    if id:
      try:
        if request.user and request.user.id:
          expense_category = ExpenseCategory.objects.get(owner=request.user, id=id)
        else:
          expense_category = ExpenseCategory.objects.get(owner=None, id=id)
      except Exception as e:
        print(str(e))
        messages.error(request, str(e))
        return render(request, self.template_name, self.response_dict)
    else:
      expense_category = None

    self.response_dict[self.ResponseDict.FORM] = self.form_class(instance=expense_category)
    self.response_dict[self.ResponseDict.CATEGORY] = expense_category

    return render(request, self.template_name, self.response_dict)

  def post(self, request, *args, **kwargs):

    id = request.POST.get('id')

    if id:
      try:
        if request.user and request.user.id:
          expense_category = ExpenseCategory.objects.get(owner=request.user, id=id)
        else:
          expense_category = ExpenseCategory.objects.get(owner=None, id=id)
      except Exception as e:
        print("uhoh: {}".format(e))
    else:
      expense_category = ExpenseCategory(owner=request.user)

    form = self.form_class(data=request.POST, instance=expense_category)

    if form.is_valid():
      form.save()
      query_string = "?id={}".format(form.instance.id)
      return HttpResponseRedirect(reverse(self.success_page) + query_string)
    else:
      self.response_dict[self.ResponseDict.FORM] = form
      return render(request, self.template_name, self.response_dict)


class ExpenseListView(TemplateView):

  class ResponseDict(str, Enum):
    LIST = 'expense_list'
    EXPENSES = 'expenses'

  template_name = settings.DEMOS_EXPENSES_EXPENSE_LIST_TEMPLATE

  def __init__(self, *args, **kwargs):
    self.response_dict = {}

  def get(self, request, *args, **kwargs):
    print("{}.get()".format(self.__class__.__name__))
    id = request.GET.get('id')

    if id:
      try:
        if request.user and request.user.id:
          expense_list = ExpenseList.objects.get(owner=request.user, id=id)
          expenses = Expense.objects.filter(owner=request.user, list=expense_list)
        else:
          expense_list = ExpenseList.objects.get(owner=None, id=id)
          expenses = Expense.objects.filter(owner=None, list=expense_list)
      except Exception as e:
        print(str(e))
        messages.error(request, str(e))
        return render(request, self.template_name, self.response_dict)
    else:
      expense_list = None
      expenses = None

    self.response_dict[self.ResponseDict.LIST] = expense_list
    self.response_dict[self.ResponseDict.EXPENSES] = expenses

    return render(request, self.template_name, self.response_dict)


class ExpenseListEditView(TemplateView):
  class ResponseDict(str, Enum):
    FORM = 'form'
    LIST = 'expense_list'

  form_class = ExpenseListForm
  template_name = settings.DEMOS_EXPENSES_EXPENSE_LIST_EDIT_TEMPLATE
  success_page = "demos:expenses:list_view"

  def __init__(self, *args, **kwargs):
    self.response_dict = {}

  def get(self, request, *args, **kwargs):
    print("{}.get()".format(self.__class__.__name__))
    id = request.GET.get('id')

    if id:
      try:
        if request.user and request.user.id:
          expense_list = ExpenseList.objects.get(owner=request.user, id=id)
        else:
          expense_list = ExpenseList.objects.get(owner=None, id=id)
      except Exception as e:
        print(str(e))
        messages.error(request, str(e))
        return render(request, self.template_name, self.response_dict)
    else:
      expense_list = None

    self.response_dict[self.ResponseDict.FORM] = self.form_class(instance=expense_list)
    self.response_dict[self.ResponseDict.LIST] = expense_list

    return render(request, self.template_name, self.response_dict)

  def post(self, request, *args, **kwargs):

    id = request.POST.get('id')

    if id:
      try:
        if request.user and request.user.id:
          expense_list = ExpenseList.objects.get(owner=request.user, id=id)
        else:
          expense_list = ExpenseList.objects.get(owner=None, id=id)
      except Exception as e:
        print("uhoh: {}".format(e))
    else:
      expense_list = ExpenseList(owner=request.user)

    form = self.form_class(data=request.POST, instance=expense_list)

    if form.is_valid():
      form.save()
      query_string = "?id={}".format(form.instance.id)
      return HttpResponseRedirect(reverse(self.success_page) + query_string)
    else:
      self.response_dict[self.ResponseDict.FORM] = form
      return render(request, self.template_name, self.response_dict)


class ExpenseEditView(TemplateView):

  class ResponseDict(str, Enum):
    FORM = 'form'
    FORMSET = 'formset'
    EXPENSES = 'expenses'

  form_class = ExpenseForm 
  success_page = 'demos:expenses:edit'
  view_page = 'demos:expenses:home'
  template_name = settings.DEMOS_EXPENSES_EXPENSE_EDIT_TEMPLATE

  def __init__(self, *args, **kwargs):
    self.response_dict = {}

  def get(self, request, *args, **kwargs):
    print("{}.get()".format(self.__class__.__name__))
    id = request.GET.get('id')

    if id:
      try:
        if request.user and request.user.id:
          expenses = Expense.objects.get(owner=request.user, id=id)
        else:
          expenses = Expense.objects.get(owner=None, id=id)
      except Exception as e:
        print(str(e))
        messages.error(request, str(e))
        return render(request, self.template_name, self.response_dict)

    formset = modelformset_factory(Expense, form=ExpenseForm, extra=5,exclude=['id','owner'],can_delete=True)

    #self.response_dict[self.ResponseDict.FORMSET] = formset(queryset=Expense.objects.filter(invoice=invoice),initial=[])
    self.response_dict[self.ResponseDict.FORMSET] = formset()

    return render(request, self.template_name, self.response_dict)

  def post(self, request, *args, **kwargs):

    owner = request.user

    try:
      expenses = Expense.objects.get(owner=owner)
    except Exception as e:
      print("uhoh: {}".format(e))
      return render(request, self.template_name, self.response_dict)

    expenses_formset = modelformset_factory(
      Expense,
      extra=5,
      exclude=['id','owner'],
      can_delete=True,
      widgets={
        }
      )

    print("POST: {}".format(request.POST))
    formset = expenses_formset(request.POST,initial=[])

    if formset.is_valid():
      print("Formset: is_valid()")
      expenses = formset.save(commit=False)
      for expense in expenses:
        expense.owner = owner
        print("Formset: save()")
        expense.save()
      for expenses in formset.deleted_objects:
        print("Formset: delete()")
        expense.delete()

      print("Formset: {} changed_objects, {} deleted_objects, {} new_objects".format(formset.changed_objects, formset.deleted_objects, formset.new_objects))
      if formset.changed_objects or formset.deleted_objects or formset.new_objects:
        messages.info(request, "Invoice updated: {} added, {} changed, {} deleted".format(len(formset.new_objects),len(formset.changed_objects),len(formset.deleted_objects)))
      else:
        messages.info(request, "No changes were made.")
      query_string = ""
      return HttpResponseRedirect(reverse(self.success_page) + query_string)
    else:
      print("Formset not valid")
      print(formset.errors)
      print("template_name: {}".format(self.template_name))
      messages.error(request, "Please fix the errors shown below.")

      self.response_dict[self.ResponseDict.FORMSET] = formset
      return render(request, self.template_name, self.response_dict)
