from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.template.context import RequestContext
from django.views.generic import FormView
from django.views.generic.base import TemplateResponseMixin
from enum import Enum
from .forms import SeleniumForm
from ..conf import settings

class SeleniumView(FormView, TemplateResponseMixin):

  class ResponseDict(str, Enum):
    FORM = 'form'

  form_class = SeleniumForm
  template_name = settings.DEMOS_SELENIUM_TEMPLATE
  success_url = '.'

  def __init__(self, *args, **kwargs):
    self.response_dict = {}

    return super(FormView, self).__init__(*args, **kwargs)

  def get(self, request, *args, **kwargs):
    form = self.form_class(request.user, data=request.GET)
    self.response_dict[self.ResponseDict.FORM] = form
    if form.is_valid():
      form.process()
    return render(request, self.template_name, self.response_dict)

  def post(self, request, *args, **kwargs):
    form = self.form_class(request.user, data=request.POST)
    self.response_dict[self.ResponseDict.FORM] = form
    if form.is_valid():
      form.process()
    return render(request, self.template_name, self.response_dict)
