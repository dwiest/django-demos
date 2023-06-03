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
from .models import NewsItem
from ..conf import settings

class NewsItemListView(ListView):

  class ResponseDict(str, Enum):
    NEWS_ITEMS = 'news'

  template_name = settings.DEMOS_NEWS_ITEM_LIST_TEMPLATE

  def setup(self, request, *args, **kwargs):
    super().setup(request, *args, **kwargs)

    if request.user.id:
      self.user = request.user

  def get_template_names(self):
    return [self.template_name]

  def get_queryset(self):
    if self.user:
      owner_q = Q(owner=self.user)
    else:
      owner_q = Q(owner=self.none)

    items = NewsItem.objects.filter(owner_q)
    return items 

  def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    context[self.ResponseDict.NEWS_ITEMS] = self.get_queryset()
    print(context)
    return context


class NewsItemView(TemplateView):

  class ResponseDict(str, Enum):
    NEWS_ITEM = 'news'

  template_name = settings.DEMOS_NEWS_ITEM_TEMPLATE

  def __init__(self, *args, **kwargs):
    self.response_dict = {}

  def get(self, request, *args, **kwargs):
    news_id = request.GET.get('id')

    if news_id:
      try:
        if request.user and request.user.id:
          news = NewsItem.objects.get(owner=request.user, id=news_id, status=0)
        else:
          news = NewsItem.objects.get(owner=None, id=news_id, status=0)
        print(news)

      except Exception as e:
        print(str(e))
        messages.error(request, str(e))
        return render(request, self.template_name, self.response_dict)
    else:
      print("Shouldn't be here")
      news = NewsItem(owner=request.user)

    self.response_dict[self.ResponseDict.NEWS_ITEM] = news

    return render(request, self.template_name, self.response_dict)


class NewsEditView(TemplateView):

  class ResponseDict(str, Enum):
    FORM = 'form'

  form_class = NewsItemForm 
  success_page = 'demos:news:home'
  template_name = settings.DEMOS_NEWS_ITEM_EDIT_TEMPLATE

  def __init__(self, *args, **kwargs):
    self.response_dict = {}

  def get(self, request, *args, **kwargs):
    news_id = request.GET.get('id')

    if news_id:
      if request.user and request.user.id:
        news = NewsItem.objects.get(owner=request.user, id=news_id)
      else:
        news = NewsItem(owner=None, id=news_id)
    else:
      if request.user and request.user.id:
        news = NewsItem(owner=request.user)
      else:
        news = NewsItem(owner=None)

    form = self.form_class(instance=news)
    self.response_dict[self.ResponseDict.FORM] = form

    return render(request, self.template_name, self.response_dict)

  def post(self, request, *args, **kwargs):
    news_id = request.POST.get('id',None)

    if news_id:
      if request.user and request.user.id:
        news = NewsItem.objects.get(owner=request.user, id=news_id)
      else:
        news = NewsItem.objects.get(owner=None, id=news_id)
    else:
      if request.user and request.user.id:
        news = Newsitem(owner=request.user)
      else:
        news = Newsitem(owner=None)

    form = self.form_class(instance=journal, data=request.POST)

    if form.is_valid():
      print("is_valid()")
      try:
        form.save()
      except Exception as e:
        print(str(e))
      messages.info(request, "News item was successfully updated.")
      #query_string = "?id={}".format(news.id)
      #return HttpResponseRedirect(reverse(self.success_page) + query_string)
      return HttpResponseRedirect(reverse(self.success_page))
    else:
      print("not_valid()")
      return render(request, self.template_name, self.response_dict)


class NewsItemView(TemplateView):

  class ResponseDict(str, Enum):
    NEWS = 'news'

  template_name = settings.DEMOS_NEWS_ITEM_TEMPLATE

  def __init__(self, *args, **kwargs):
    self.response_dict = {}

  def get(self, request, *args, **kwargs):
    news_id = request.GET.get('id')

    if news_id:
      try:
        news = NewsItem.objects.get(owner=request.user, id=news_id)
      except Exception as e:
        print(str(e))
        messages.error(request, str(e))
        return render(request, self.template_name, self.response_dict)
    else:
      news = NewsItem(owner=request.user)

    self.response_dict[self.ResponseDict.NEWS] = news 

    return render(request, self.template_name, self.response_dict)


class NewsItemEditView(TemplateView):

  class ResponseDict(str, Enum):
    FORM = 'form'

  form_class = NewsItemForm 
  success_page = 'demos:news:view'
  template_name = settings.DEMOS_NEWS_ITEM_EDIT_TEMPLATE

  def __init__(self, *args, **kwargs):
    self.response_dict = {}

  def get(self, request, *args, **kwargs):
    print("NewsItemEditView.get()")
    news_id = request.GET.get('id')

    if news_id:
      try:
        if request.user and request.user.id:
          news = NewsItem.objects.get(owner=request.user, id=news_id)
        else:
          news = NewsItem.objects.get(owner=None, id=news_id)
      except Exception as e:
        print(str(e))
        messages.error(request, str(e))
        return render(request, self.template_name, self.response_dict)
    else:
      news = NewsItem(owner=request.user)

    form = self.form_class(instance=news)

    self.response_dict[self.ResponseDict.FORM] = form

    return render(request, self.template_name, self.response_dict)

  def post(self, request, *args, **kwargs):
    if request.POST.get('id'):
      news = NewsItem.objects.get(owner=request.user, id=request.POST.get('id'))
    else:
      news = NewsItem(owner=request.user)
    form = self.form_class(instance=news, data=request.POST)

    if form.is_valid():
      print("is_valid()")
      form.save()
      messages.info(request, "News item was successfully updated.")
      query_string = "?id={}".format(form.instance.id)
      return HttpResponseRedirect(reverse(self.success_page) + query_string)
    else:
      print("not_valid()")
      return render(request, self.template_name, self.response_dict)
