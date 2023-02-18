from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.template.context import RequestContext
from django.views.generic import FormView
from django.views.generic.base import TemplateResponseMixin
from .forms import QrcodeForm

class QrcodeView(LoginRequiredMixin, FormView, TemplateResponseMixin):
  form_class = QrcodeForm
  page_name = 'QR Code'
  template_name = "dwiest-django-demos/qrcode/index.html"
  success_url = '.'

  def __init__(self, *args, **kwargs):
    self.response_dict = {
      'page_name': self.page_name,
    }

    return super(FormView, self).__init__(*args, **kwargs)

  def get(self, request, *args, **kwargs):
    form = QrcodeForm()
    self.response_dict['form'] = form
    return render(request, self.template_name, self.response_dict)


  def post(self, request, *args, **kwargs):
    form = QrcodeForm(data=request.POST)
    self.response_dict['form'] = form
    if form.is_valid():
      form.process()
      return render(request, self.template_name, self.response_dict)
    else:
      return render(request, self.template_name, self.response_dict)
