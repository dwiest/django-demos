from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.template.context import RequestContext
from django.views.generic import FormView
from django.views.generic.base import TemplateResponseMixin
from .forms import SeleniumForm
from ..conf import settings

class SeleniumView(FormView, TemplateResponseMixin):
  form_class = SeleniumForm
  page_name = 'Selenium'
  template_name = settings.DEMOS_SELENIUM_TEMPLATE
  success_url = '.'

  def __init__(self, *args, **kwargs):
    self.response_dict = {
      'page_name': self.page_name,
      'static_url' : settings.STATIC_URL,
    }

    return super(FormView, self).__init__(*args, **kwargs)


  def get(self, request, *args, **kwargs):
    width = request.GET.get('w', None)
    height = request.GET.get('h', None)
    form = SeleniumForm(request.user, width=width, height=height)
    self.response_dict['form'] = form
    return render(request, self.template_name, self.response_dict)

  def post(self, request, *args, **kwargs):
    form = SeleniumForm(request.user, data=request.POST)
    self.response_dict['form'] = form
    if form.is_valid():
      form.screenshot()
      query_string = '?w={}&h={}'.format(form.cleaned_data['width'], form.cleaned_data['height'])
      return HttpResponseRedirect(request.path + query_string)
    else:
      return render(request, self.template_name, self.response_dict)
