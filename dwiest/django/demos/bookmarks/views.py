from django.http import HttpResponseRedirect
from django.shortcuts import render, reverse
from django.template.context import RequestContext
from django.views.generic import FormView, TemplateView
from django.views.generic.base import TemplateResponseMixin
from enum import Enum
from .forms import BookmarkForm
from .models import Bookmark
from ..conf import settings

class BookmarksView(TemplateView):#FormView, TemplateResponseMixin):

  class ResponseDict(str, Enum):
    BOOKMARKS = 'bookmarks'
    FORM = 'form'

  form_class = BookmarkForm
  template_name = settings.DEMOS_BOOKMARKS_TEMPLATE

  def __init__(self, *args, **kwargs):
    self.response_dict = {}
    return super(TemplateView, self).__init__(*args, **kwargs)

  def get(self, request, *args, **kwargs):
    form = self.form_class()
    bookmarks = Bookmark.objects.all()
    self.response_dict[self.ResponseDict.BOOKMARKS] = bookmarks
    self.response_dict[self.ResponseDict.FORM] = form 
    return render(request, self.template_name, self.response_dict)

class AddBookmarkView(FormView, TemplateResponseMixin):

  class ResponseDict(str, Enum):
    FORM = 'form'

  form_class = BookmarkForm

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
