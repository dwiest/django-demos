from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist
from django.http import FileResponse, HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.views.generic import FormView, TemplateView
import os

from ..conf import settings
from .forms import FileUploadForm, FileDetailsForm
from .models import File, FileQuota, FileSummary


home_page = 'file'
detail_page = 'file/details'


class FileIndexView(TemplateView):
  page_name = 'Files'
  template_name = 'dwiest-django-demos/file/index.html'
  form_class = FileUploadForm
  success_page = 'demos:file:index'
  error_page = success_page

  def __init__(self, *args, **kwargs):
    self.response_dict = {
      'page_name': self.page_name,
      }

  def get(self, request, *args, **kwargs):
    form = self.form_class()
    self.response_dict['form'] = form

    summaries = FileSummary.objects.filter(owner=request.user)
    if len(summaries) == 1:
      self.response_dict['summary'] = summaries[0]
    else:
      messages.error(request, "Couldn't load file summary")

    files = File.objects.filter(owner=request.user)
    self.response_dict['files'] = files

    quotas = FileQuota.objects.filter(id=1)
    if len(quotas) == 1:
      self.response_dict['quota'] = quotas[0]
    else:
      self.response_dict['quota'] = {max_files: 'n/a', max_filesize: 'n/a', max_total_filesize: 'n/a'}

    return render(request, self.template_name, self.response_dict)

  def post(self, request, *args, **kwargs):
    form = self.form_class(request.user, request.POST, request.FILES)
    self.response_dict['form'] = form
    if form.is_valid():
      try:
        form.save()
        messages.info(request, "{} was successfully uploaded.".format(form.cleaned_data['file'].name))
        return HttpResponseRedirect(reverse(self.success_page))
      except Exception as e:
        print(str(e))
        messages.error(request, str(e))
        return HttpResponseRedirect(reverse(self.error_page))
    else:
      messages.error(request, "{} could not be uploaded.".format(form.cleaned_data['file'].name))
      for error in form.errors['__all__']:
        messages.error(request, error)
      return HttpResponseRedirect(reverse(self.error_page))
      #return render(request, self.template_name, self.response_dict)


class FileDetailView(TemplateView):
  '''
    Display the details of an uploaded file
  '''

  page_name = 'File Details'
  template_name = 'dwiest-django-demos/file/details.html'
  success_page = 'demos:file:details'
  error_page = 'demos:file:index'


  def __init__(self, *args, **kwargs):
    self.response_dict = {
      'page_name': self.page_name,
      }


  def get(self, request, *args, **kwargs):
    path = request.GET.get('path')

    if path:
      try:
        file = File.objects.get(owner=request.user, path=path)
        form = FileDetailsForm(instance=file)
        self.response_dict['file'] = file
        self.response_dict['form'] = form
      except Exception as e:
        print(str(e))
        messages.error(request, str(e))
        return HttpResponseRedirect(reverse(self.error_page))
    else:
      messages.error(request, 'A file path was not specified.')
      return HttpResponseRedirect(reverse(self.error_page))

    return render(request, self.template_name, self.response_dict)

  def post(self, request, *args, **kwargs):
    file = File.objects.get(owner=request.user, path=request.POST['path'])
    self.response_dict['file'] = file
    form = FileDetailsForm(instance=file, data=request.POST)
    if form.is_valid():
      form.save()
      messages.info(request, "{} was successfully updated.".format(file.name))
      query_string = "?path={}".format(file.path)
      return HttpResponseRedirect(reverse(self.success_page) + query_string)
    else:
      return render(request, self.template_name, self.response_dict)


class FileDeleteView(TemplateView):
  '''
    Deletes an uploaded file
  '''

  page_name = 'Delete File'
  success_page = 'demos:file:index'
  error_page = 'demos:file:details'


  def __init__(self, *args, **kwargs):
    self.response_dict = {
      'page_name': self.page_name,
      }


  def get(self, request, *args, **kwargs):
    path = request.GET.get('path')

    if path:
      try:
        file = File.objects.get(owner=request.user, path=path)
        # update summary
        summaries = FileSummary.objects.filter(owner=request.user)
        if len(summaries) == 1:
          summary = summaries[0]
          summary.files -= 1
          summary.size -= file.size
          summary.save()
        else:
          pass # shouldn't happen!
        # remove from filesystem
        os.remove('/tmp/' + file.path)
        # remove file record
        file.delete()
      except Exception as e:
        print(str(e))
        messages.error(request, str(e))
        return HttpResponseRedirect(reverse(self.error_page))
    else:
      messages.error(request, 'A file path was not specified.')
      return HttpResponseRedirect(reverse(self.error_page), self.response_dict)

    messages.warning(request, "{} was deleted".format(file.name))
    return HttpResponseRedirect(reverse(self.success_page), self.response_dict)


class FileDownloadView(TemplateView):
  '''
    Downloads an uploaded file
  '''

  success_page = 'demos:file:index'
  error_page = success_page

  def get(self, request, *args, **kwargs):
    path = request.GET.get('path')

    if path:
      try:
        file = File.objects.get(owner=request.user, path=path)
      except Exception as e:
        print(str(e))
        messages.error(request, str(e))
        return HttpResponseRedirect(reverse(self.error_page))
    else:
      messages.error(request, 'A file path was not specified.')
      return HttpResponseRedirect(reverse(self.error_page), self.response_dict)

    content = open("/tmp/" + file.path, 'rb')
    response = FileResponse(content)
    response['Content-Type'] = file.content_type
    response['Content-Length'] = file.size
    response['Content-Disposition'] = 'attachment; filename={}'.format(file.name)
    return response


class FileOpenView(TemplateView):
  '''
    Opens an uploaded file
  '''

  success_page = 'demos:file:index'
  error_page = success_page

  def get(self, request, *args, **kwargs):
    path = request.GET.get('path')

    if path:
      try:
        file = File.objects.get(owner=request.user, path=path)
      except Exception as e:
        print(str(e))
        messages.error(request, str(e))
        return HttpResponseRedirect(reverse(self.error_page))
    else:
      messages.error(request, 'A file path was not specified.')
      return HttpResponseRedirect(reverse(self.error_page), self.response_dict)

    content = open("/tmp/" + file.path, "rb")
    response = FileResponse(content, filename=file.name)
    response['Content-Type'] = file.content_type
    response['Content-Length'] = file.size
    return response
