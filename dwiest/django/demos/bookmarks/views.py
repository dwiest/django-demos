from django.contrib import messages
from django.http import HttpResponseRedirect
from django.shortcuts import render, reverse
from django.template.context import RequestContext
from django.views.generic import FormView, TemplateView
from django.views.generic.base import TemplateResponseMixin
from enum import Enum
from .forms import *
from .models import Bookmark
from ..conf import settings

class BookmarksView(TemplateView):

  class ResponseDict(str, Enum):
    BOOKMARKS = 'bookmarks'
    FORM = 'form'

  form_class = QuickBookmarkForm
  template_name = settings.DEMOS_BOOKMARKS_TEMPLATE

  def __init__(self, *args, **kwargs):
    self.response_dict = {}
    return super(TemplateView, self).__init__(*args, **kwargs)

  def get(self, request, *args, **kwargs):
    form = self.form_class()
    if request.user and request.user.id:
      bookmarks = Bookmark.objects.filter(owner=request.user)
    else:
      bookmarks = Bookmark.objects.filter(owner=None)
    self.response_dict[self.ResponseDict.BOOKMARKS] = bookmarks
    self.response_dict[self.ResponseDict.FORM] = form 
    return render(request, self.template_name, self.response_dict)


class QuickAddBookmarkView(FormView, TemplateResponseMixin):

  class ResponseDict(str, Enum):
    FORM = 'form'

  form_class = QuickBookmarkForm

  def __init__(self, *args, **kwargs):
    self.response_dict = {}
    return super(FormView, self).__init__(*args, **kwargs)

  def post(self, request, *args, **kwargs):
    form = self.form_class(data=request.POST)
    self.response_dict[self.ResponseDict.FORM] = form
    if form.is_valid():
      form.process()
      form.save()
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
