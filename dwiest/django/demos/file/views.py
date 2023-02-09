from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist
from django.http import FileResponse, HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.views.generic import FormView, TemplateView

from ..conf import settings
from .forms import FileUploadForm
from .models import File


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
    files = File.objects.filter(owner=request.user)
    self.response_dict['files'] = files
    return render(request, self.template_name, self.response_dict)

  def post(self, request, *args, **kwargs):
    form = self.form_class(request.user, request.POST, request.FILES)
    self.response_dict['form'] = form
    if form.is_valid():
      try:
        form.save()
        messages.info(request, "File uploaded successfully.")
        return HttpResponseRedirect(reverse(self.success_page))
      except Exception as e:
        print(str(e))
        messages.error(request, str(e))
        return HttpResponseRedirect(reverse(self.error_page))
    else:
      messages.error(request, "Form wasn't valid?")
      return render(request, self.template_name, self.response_dict)


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
        self.response_dict['file'] = file
      except Exception as e:
        print(str(e))
        messages.error(request, str(e))
        return HttpResponseRedirect(reverse(self.error_page))
    else:
      messages.error(request, 'A file path was not specified.')
      return HttpResponseRedirect(reverse(self.error_page), self.response_dict)

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
        #file.delete()
        # delete file here
      except Exception as e:
        print(str(e))
        messages.error(request, str(e))
        return HttpResponseRedirect(reverse(self.error_page))
    else:
      messages.error(request, 'A file path was not specified.')
      return HttpResponseRedirect(reverse(self.error_page), self.response_dict)

    messages.info(request, "{} was deleted".format(file.name))
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
