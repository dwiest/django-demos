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
from .models import Journal, JournalEntry
from ..conf import settings

class JournalListView(ListView):

  class ResponseDict(str, Enum):
    JOURNALS = 'journals'

  template_name = settings.DEMOS_JOURNAL_LIST_TEMPLATE
  user = None

  def setup(self, request, *args, **kwargs):
    super().setup(request, *args, **kwargs)

    if request.user.id:
      self.user = request.user

  def get_template_names(self):
    return [self.template_name]

  def get_queryset(self):
    if self.user:
      owner_q = Q(owner=self.user, status=0)
    else:
      owner_q = Q(owner=None, status=0)

    journals = Journal.objects.filter(owner_q)
    return journals

  def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    context[self.ResponseDict.JOURNALS] = self.get_queryset()
    return context


class JournalView(TemplateView):

  class ResponseDict(str, Enum):
    JOURNAL = 'journal'
    ENTRIES = 'entries'

  template_name = settings.DEMOS_JOURNAL_TEMPLATE

  def __init__(self, *args, **kwargs):
    self.response_dict = {}

  def get(self, request, *args, **kwargs):
    journal_id = request.GET.get('id')

    if journal_id:
      try:
        if request.user and request.user.id:
          journal = Journal.objects.get(owner=request.user, id=journal_id, status=0)
          entries = JournalEntry.objects.filter(owner=request.user, journal=journal_id, status=0)
        else:
          journal = Journal.objects.get(owner=None, id=journal_id, status=0)
          entries = JournalEntry.objects.filter(owner=None, journal=journal_id, status=0)

      except Exception as e:
        print(str(e))
        messages.error(request, str(e))
        return render(request, self.template_name, self.response_dict)
    else:
      journal = Journal()
      entries = []

    self.response_dict[self.ResponseDict.JOURNAL] = journal
    self.response_dict[self.ResponseDict.ENTRIES] = entries

    return render(request, self.template_name, self.response_dict)


class JournalEditView(TemplateView):

  class ResponseDict(str, Enum):
    FORM = 'form'

  form_class = JournalForm 
  success_page = 'demos:journal:home'
  template_name = settings.DEMOS_JOURNAL_EDIT_TEMPLATE

  def __init__(self, *args, **kwargs):
    self.response_dict = {}

  def get(self, request, *args, **kwargs):
    journal_id = request.GET.get('id')

    if journal_id:
      if request.user and request.user.id:
        journal = Journal.objects.get(owner=request.user, id=journal_id)
      else:
        journal = Journal(owner=None, id=journal_id)
    else:
      if request.user and request.user.id:
        journal = Journal(owner=request.user)
      else:
        journal = Journal(owner=None)

    form = self.form_class(instance=journal)
    self.response_dict[self.ResponseDict.FORM] = form

    return render(request, self.template_name, self.response_dict)

  def post(self, request, *args, **kwargs):
    journal_id = request.POST.get('id',None)

    if journal_id:
      if request.user and request.user.id:
        journal = Journal.objects.get(owner=request.user, id=journal_id)
      else:
        journal = Journal.objects.get(owner=None, id=journal_id)
    else:
      if request.user and request.user.id:
        journal = Journal(owner=request.user)
      else:
        journal = Journal(owner=None)

    form = self.form_class(instance=journal, data=request.POST)

    if form.is_valid():
      print("is_valid()")
      try:
        form.save()
      except Exception as e:
        print(str(e))
      messages.info(request, "Journal was successfully updated.")
      #query_string = "?id={}".format(journal.id)
      #return HttpResponseRedirect(reverse(self.success_page) + query_string)
      return HttpResponseRedirect(reverse(self.success_page))
    else:
      print("not_valid()")
      return render(request, self.template_name, self.response_dict)


class JournalEntryView(TemplateView):

  class ResponseDict(str, Enum):
    ENTRY = 'entry'

  template_name = settings.DEMOS_JOURNAL_ENTRY_TEMPLATE

  def __init__(self, *args, **kwargs):
    self.response_dict = {}

  def get(self, request, *args, **kwargs):
    entry_id = request.GET.get('id')

    if entry_id:
      try:
        entry = JournalEntry.objects.get(id=entry_id)
      except Exception as e:
        print(str(e))
        messages.error(request, str(e))
        return render(request, self.template_name, self.response_dict)
    else:
      entry = JournalEntry()

    self.response_dict[self.ResponseDict.ENTRY] = entry

    return render(request, self.template_name, self.response_dict)


class JournalEntryEditView(TemplateView):

  class ResponseDict(str, Enum):
    FORM = 'form'

  form_class = JournalEntryForm 
  success_page = 'demos:journal:view'
  template_name = settings.DEMOS_JOURNAL_ENTRY_EDIT_TEMPLATE

  def __init__(self, *args, **kwargs):
    self.response_dict = {}

  def get(self, request, *args, **kwargs):
    entry_id = request.GET.get('id')

    if entry_id:
      try:
        if request.user and request.user.id:
          entry = JournalEntry.objects.get(owner=request.user, id=entry_id)
        else:
          entry = JournaEntry.objects.get(owner=None, id=entry_id)
      except Exception as e:
        print(str(e))
        messages.error(request, str(e))
        return render(request, self.template_name, self.response_dict)
    else:
      entry = JournalEntry()

    form = self.form_class(instance=entry)

    self.response_dict[self.ResponseDict.FORM] = form

    return render(request, self.template_name, self.response_dict)

  def post(self, request, *args, **kwargs):
    if request.POST.get('id'):
      entry = JournalEntry.objects.get(owner=request.user, id=request.POST.get('id'))
    else:
      journal = Journal.objects.get(owner=request.user, id=request.POST.get('journal'))
      entry = JournalEntry(owner=request.user, journal=journal)
    form = self.form_class(instance=entry, data=request.POST)

    if form.is_valid():
      print("is_valid()")
      form.save()
      messages.info(request, "Entry was successfully updated.")
      query_string = "?id={}".format(form.instance.journal.id)
      return HttpResponseRedirect(reverse(self.success_page) + query_string)
    else:
      print("not_valid()")
      return render(request, self.template_name, self.response_dict)
