from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.template.context import RequestContext
from django.views.generic import FormView
from django.views.generic.base import TemplateResponseMixin
from .forms import SeleniumForm

class SeleniumView(FormView, TemplateResponseMixin):
  form_class = SeleniumForm
  page_name = 'Selenium'
  template_name = "dwiest-django-demos/selenium/index.html"
  success_url = '.'

  def __init__(self, *args, **kwargs):
    self.response_dict = {
      'page_name': self.page_name,
    }

    return super(FormView, self).__init__(*args, **kwargs)


  def get(self, request, *args, **kwargs):
    print("SeleniumView.get()")
    form = SeleniumForm(request.user)
    self.response_dict['form'] = form
    return render(request, self.template_name, self.response_dict)

  def post(self, request, *args, **kwargs):
    print("SeleniumView.post()")
    form = SeleniumForm(request.user, request.POST)
    self.response_dict['form'] = form
    if form.is_valid():
      form.screenshot()
      return HttpResponseRedirect(request.path)
    else:
      return render(request, self.template_name, self.response_dict)
