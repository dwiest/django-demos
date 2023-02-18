from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.template.context import RequestContext
from django.views.generic import FormView
from django.views.generic.base import TemplateResponseMixin
from .forms import OtpForm
from ..conf import settings

class OtpView(LoginRequiredMixin, FormView, TemplateResponseMixin):
  form_class = OtpForm
  page_name = 'OTP'
  template_name = settings.DEMOS_OTP_TEMPLATE
  success_url = '.'

  def __init__(self, *args, **kwargs):
    self.response_dict = {
      'page_name': self.page_name,
    }

    return super(FormView, self).__init__(*args, **kwargs)

  def get(self, request, *args, **kwargs):
    form = OtpForm()
    self.response_dict['form'] = form
    return render(request, self.template_name, self.response_dict)

  def post(self, request, *args, **kwargs):
    form = OtpForm(data=request.POST)
    self.response_dict['form'] = form
    if form.is_valid():
      form.process()
      return render(request, self.template_name, self.response_dict)
    else:
      return render(request, self.template_name, self.response_dict)
