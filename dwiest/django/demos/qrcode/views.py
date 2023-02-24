from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.template.context import RequestContext
from django.views.generic import FormView
from django.views.generic.base import TemplateResponseMixin
from enum import Enum
from .forms import QrcodeForm
from ..conf import settings

class QrcodeView(FormView, TemplateResponseMixin):

  class ResponseDict(str, Enum):
    FORM = 'form'

  form_class = QrcodeForm
  template_name = settings.DEMOS_QRCODE_TEMPLATE

  def __init__(self, *args, **kwargs):
    self.response_dict = {}
    return super(FormView, self).__init__(*args, **kwargs)

  def get(self, request, *args, **kwargs):
    form = QrcodeForm(data=request.GET)
    self.response_dict[self.ResponseDict.FORM] = form
    return render(request, self.template_name, self.response_dict)

  def post(self, request, *args, **kwargs):
    form = QrcodeForm(data=request.POST)
    self.response_dict[self.ResponseDict.FORM] = form
    if form.is_valid():
      form.process()
    return render(request, self.template_name, self.response_dict)
