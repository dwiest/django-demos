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


class JournalView(ListView):

  class ResponseDict(str, Enum):
    ENTRIES = 'entries'
    FILTER = 'filter'
    JOURNAL = 'journal'

  template_name = settings.DEMOS_JOURNAL_TEMPLATE

  def __init__(self, *args, **kwargs):
    self.response_dict = {}
    super().__init__(*args,**kwargs)

  def setup(self, request, *args, **kwargs):
    super().setup(request, *args, **kwargs)

    if request.user.id:
      self.user = request.user
    else:
      self.user = None

    journal_id = request.GET.get('id')

    if journal_id:
      try:
        if request.user and request.user.id:
          self.journal = Journal.objects.get(owner=request.user, id=journal_id, status=0)
          #self.entries = JournalEntry.objects.filter(owner=request.user, journal=journal_id, status=0)
        else:
          self.journal = Journal.objects.get(owner=None, id=journal_id, status=0)
          #self.entries = JournalEntry.objects.filter(owner=None, journal=journal_id, status=0)

      except Exception as e:
        print(str(e))
        messages.error(request, str(e))
        return render(request, self.template_name, self.response_dict)
    else:
      self.journal = Journal()
      #self.entries = []

    if request.session.get('journal_filter'):
      print("filter present")
      if request.GET.get('filter'):
        bff = JournalFilterForm(data=request.GET)
      else:
        f = request.session['journal_filter']
        new_data = request.GET.copy()
        new_data['filter'] = f
        if f == 'date':
          new_data['month'] = request.session.get('journal_filter_month')
          new_data['year'] = request.session.get('journal_filter_year')
        bff = JournalFilterForm(data=new_data)
    else:
      bff = JournalFilterForm(data=request.GET)

    self.filter = bff

    if self.filter.is_valid():
      filter = self.filter.cleaned_data['filter']
      print(filter)

      if filter == 'undated':
        self.filter_q = Q(date=None)
        request.session['journal_filter'] = 'undated'

      elif filter == 'untitled':
        self.filter_q = Q(title='')
        request.session['journal_filter'] = 'untitled'

      elif filter == 'date':
        month = self.filter.cleaned_data['month']
        year = self.filter.cleaned_data['year']
        request.session['journal_filter_month'] = month
        request.session['journal_filter_year'] = year

        if month and int(month) > 0:
          start_dt = datetime(int(year), int(month), 1)
          if month == 12:
            end_dt = datetime(int(year) + 1, 1, 1)
          else:
            end_dt = datetime(int(year), int(month) + 1, 1)

        else:
          start_dt = datetime(int(year), 1, 1)
          end_dt = datetime(int(year) + 1, 1, 1)

        self.filter_q = Q(date__gte=start_dt) & Q(date__lt=end_dt)

        request.session['journal_filter'] = 'date'

      elif filter == 'none':
        request.session['journal_filter'] = 'none'

      # deleted/hidden
      status = [0]
      if bff.cleaned_data['show_deleted']:
        status.append(-1)
      if bff.cleaned_data['show_hidden']:
        status.append(1)

      q = Q(status__in=status)

      if hasattr(self,'filter_q'):
        self.filter_q = self.filter_q & q
      else:
        self.filter_q = q

      # unread
      if bff.cleaned_data['hide_read']:
        q = Q(unread=True)

      if hasattr(self,'filter_q'):
        self.filter_q = self.filter_q & q
      else:
        self.filter_q = q

  def get_queryset(self):
    if self.user:
      owner_q = Q(owner=self.user)
    else:
      owner_q = Q(owner=None)

    entries = JournalEntry.objects.filter(owner_q)

    if hasattr(self, 'filter_q'):
      entries = entries.filter(self.filter_q)

    return entries 

  def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    context[self.ResponseDict.FILTER] = self.filter
    context[self.ResponseDict.JOURNAL] = self.journal
    context[self.ResponseDict.ENTRIES] = self.get_queryset()

    return context


#  def get(self, request, *args, **kwargs):
#    journal_id = request.GET.get('id')

#    if journal_id:
#      try:
#        if request.user and request.user.id:
#          journal = Journal.objects.get(owner=request.user, id=journal_id, status=0)
#          entries = JournalEntry.objects.filter(owner=request.user, journal=journal_id, status=0)
#        else:
#          journal = Journal.objects.get(owner=None, id=journal_id, status=0)
#          entries = JournalEntry.objects.filter(owner=None, journal=journal_id, status=0)

#      except Exception as e:
#        print(str(e))
#        messages.error(request, str(e))
#        return render(request, self.template_name, self.response_dict)
#    else:
#      journal = Journal()
#      entries = []

#    self.response_dict[self.ResponseDict.JOURNAL] = journal
#    self.response_dict[self.ResponseDict.ENTRIES] = entries

#    return render(request, self.template_name, self.response_dict)


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
