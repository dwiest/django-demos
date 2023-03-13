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
from .models import Bookmark
from ..conf import settings

class BookmarksView(ListView):

  class ResponseDict(str, Enum):
    BOOKMARKS = 'bookmarks'
    FILTER = 'filter'
    FORM = 'form'
    DAYS = 'days'
    MONTHS = 'months'
    SEARCH = 'search'
    YEARS = 'years'

  form_class = QuickBookmarkForm
  paginate_by = 40
  template_name = settings.DEMOS_BOOKMARKS_TEMPLATE

#  def __init__(self, *args, **kwargs):
#    self.response_dict = {}
#    return super(TemplateView, self).__init__(*args, **kwargs)

  def setup(self, request, *args, **kwargs):
    super().setup(request, *args, **kwargs)

    if request.user.id:
      self.user = request.user
    else:
      self.user = None

    # quick add failed
    self.url = request.GET.get('url')

    term = request.GET.get('term')
    if term:
      print("term was specified")
      self.search = BookmarkSearchForm(data=request.GET)
      if self.search.is_valid():
        self.search_q = self.search.getQ()
        request.session['bookmarks_search'] = self.search.cleaned_data.get('term')
    elif term == None and request.session.get('bookmarks_search'):
      print("term was retrieved from session")
      term = request.session['bookmarks_search']
      new_data = request.GET.copy()
      new_data['term'] = term
      self.search = BookmarkSearchForm(data=new_data)
      if self.search.is_valid():
        self.search_q = self.search.getQ()
    elif request.session.get('bookmarks_search'):
      print("removing bookmarks_search")
      del request.session['bookmarks_search']
      self.search = BookmarkSearchForm()
    else:
      self.search = BookmarkSearchForm()

    if request.session.get('bookmarks_filter'):
      print("filter present")
      if request.GET.get('filter'):
        bff = BookmarkFilterForm(data=request.GET)
      else:
        f = request.session['bookmarks_filter']
        new_data = request.GET.copy()
        new_data['filter'] = f
        if f == 'date':
          new_data['month'] = request.session.get('bookmarks_filter_month')
          new_data['year'] = request.session.get('bookmarks_filter_year')
        bff = BookmarkFilterForm(data=new_data)
    else:
      bff = BookmarkFilterForm(data=request.GET)

    self.filter = bff

    if self.filter.is_valid():
      filter = self.filter.cleaned_data['filter']
      print(filter)

      if filter == 'undated':
        self.filter_q = Q(article_date=None)
        request.session['bookmarks_filter'] = 'undated'

      elif filter == 'untitled':
        self.filter_q = Q(title='')
        request.session['bookmarks_filter'] = 'untitled'

      elif filter == 'date':
        month = self.filter.cleaned_data['month']
        year = self.filter.cleaned_data['year']
        request.session['bookmarks_filter_month'] = month
        request.session['bookmarks_filter_year'] = year

        if month and int(month) > 0:
          start_dt = datetime(int(year), int(month), 1)
          if month == 12:
            end_dt = datetime(int(year) + 1, 1, 1)
          else:
            end_dt = datetime(int(year), int(month) + 1, 1)

        else:
          start_dt = datetime(int(year), 1, 1)
          end_dt = datetime(int(year) + 1, 1, 1)

        self.filter_q = Q(article_date__gte=start_dt) & Q(article_date__lt=end_dt)

        request.session['bookmarks_filter'] = 'date'

      elif filter == 'none':
        request.session['bookmarks_filter'] = 'none'

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



  def get_template_names(self):
    return [self.template_name]

  def get_queryset(self):
    if self.user:
      owner_q = Q(owner=self.user)
    else:
      owner_q = Q(owner=self.none)

    bookmarks = Bookmark.objects.filter(owner_q)

    if hasattr(self, 'search_q'):
      bookmarks = bookmarks.filter(self.search_q)

    if hasattr(self, 'filter_q'):
      bookmarks = bookmarks.filter(self.filter_q)

    return bookmarks

  def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    if self.url:
      context[self.ResponseDict.FORM] = self.form_class(data={'url':self.url})
    else:
      context[self.ResponseDict.FORM] = self.form_class()
    context[self.ResponseDict.BOOKMARKS] = self.get_queryset()
    context[self.ResponseDict.FILTER] = self.filter
    context[self.ResponseDict.SEARCH] = self.search

    return context


#  def get(self, request, *args, **kwargs):
#    form = self.form_class()
#    if request.user and request.user.id:
#      bookmarks = Bookmark.objects.filter(owner=request.user)
#    else:
#      bookmarks = Bookmark.objects.filter(owner=None)
#    self.response_dict[self.ResponseDict.BOOKMARKS] = bookmarks
#    self.response_dict[self.ResponseDict.FORM] = form
#    return render(request, self.template_name, self.response_dict)


class QuickAddBookmarkView(FormView, TemplateResponseMixin):

  class ResponseDict(str, Enum):
    FORM = 'form'

  form_class = QuickBookmarkForm

  def __init__(self, *args, **kwargs):
    self.response_dict = {}
    return super(FormView, self).__init__(*args, **kwargs)

  def post(self, request, *args, **kwargs):
    if request.user and request.user.id:
      form = self.form_class(owner=request.user, data=request.POST)
    else:
      form = self.form_class(owner=None, data=request.POST)
    self.response_dict[self.ResponseDict.FORM] = form
    if form.is_valid():
      form.process()
      try:
        form.save()
      except ValidationError as e:
        messages.error(request, e.message)
       # return render(request, BookmarksView.template_name, self.response_dict)
        return HttpResponseRedirect(reverse('demos:bookmarks:home') + '?url={}'.format(form.cleaned_data['url']))

    messages.info(request, "Your bookmark was added.")
    return HttpResponseRedirect(reverse('demos:bookmarks:home'))


class BookmarkView(TemplateView):

  class ResponseDict(str, Enum):
    FORM = 'form'

  form_class = BookmarkForm
  success_page = 'demos:bookmarks:home'
  template_name = settings.DEMOS_BOOKMARKS_BOOKMARK_TEMPLATE

  def __init__(self, *args, **kwargs):
    self.response_dict = {}

  def get(self, request, *args, **kwargs):
    bookmark_id = request.GET.get('id')

    if bookmark_id:
      try:
        if request.user and request.user.id:
          bookmark = Bookmark.objects.get(owner=request.user, id=bookmark_id)
        else:
          bookmark = Bookmark.objects.get(owner=None, id=bookmark_id)
      except Exception as e:
        print(str(e))
        messages.error(request, str(e))
        return render(request, self.template_name, self.response_dict)
    else:
      bookmark = Bookmark()

    form = self.form_class(instance=bookmark)

    self.response_dict[self.ResponseDict.FORM] = form

    return render(request, self.template_name, self.response_dict)

  def post(self, request, *args, **kwargs):

    if request.user and request.user.id:
      bookmark = Bookmark.objects.get(owner=request.user, id=request.POST['id'])

    else:
      bookmark = Bookmark.objects.get(owner=None, id=request.POST['id'])

    form = self.form_class(instance=bookmark , data=request.POST)

    if form.is_valid():
      form.save()
      messages.info(request, "Bookmark was successfully updated.")
      query_string = "?id={}".format(bookmark.id)
      return HttpResponseRedirect(reverse(self.success_page) + query_string)

    else:
      return render(request, self.template_name, self.response_dict)
