from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.views.generic import FormView
from .forms import GRecaptchaForm
from ..conf import settings

class GRecaptchaView(FormView):
  template_name = settings.DEMOS_GOOGLE_RECAPTCHA_TEMPLATE
  success_url = '.'
  form_class = GRecaptchaForm

  def __init__(self, *args, **kwargs):
    self.response_dict = {
      'action': GRecaptchaForm.action,
      'site_key': settings.DEMOS_GOOGLE_RECAPTCHA_SITE_KEY
    }

    return super(FormView, self).__init__(*args, **kwargs)

  def get(self, request, *args, **kwargs):
    print("GRecaptchaView.get()")
    form = GRecaptchaForm()
    self.response_dict['form'] = form
    return render(request, self.template_name, self.response_dict)

  def post(self, request, *args, **kwargs):
    print("GRecaptchaView.post()")
    form = GRecaptchaForm(request.POST)
    self.response_dict['form'] = form
    if form.is_valid():
      request.session['risk_score'] = form.risk_score
      return HttpResponseRedirect(request.path)
    else:
      return render(request, self.template_name, self.response_dict)
