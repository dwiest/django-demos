from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.template.context import RequestContext
from django.views.generic import FormView
from django.views.generic.base import TemplateResponseMixin
from .forms import OtpForm, get_qrcode

class OtpView(FormView, TemplateResponseMixin):
  form_class = OtpForm
  page_name = 'OTP'
  template_name = "dwiest-django-demos/otp/index.html"
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
      self.response_dict['otp'] = form.get_otp()
      uri = form.get_provisioning_uri()
      self.response_dict['secret_key_image'] = get_qrcode(uri)
      return render(request, self.template_name, self.response_dict)
    else:
      return render(request, self.template_name, self.response_dict)
