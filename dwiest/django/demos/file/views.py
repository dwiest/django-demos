import json
from datetime import datetime, timezone
from functools import wraps
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.http import Http404, HttpResponseRedirect, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from ..application_access import for_request
from .forms import FileDetailsForm
from .storage import FileStore, StorageError
from .signals import file_updated, file_deleted


def access(view):
    @login_required
    @never_cache
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not for_request(request).allows('file'):
            return render(request, 'dwiest-django-demos/applications/denied.html', status=403)
        try:
            return view(request, *args, **kwargs)
        except StorageError as exc:
            if request.resolver_match.url_name in ('register', 'complete'):
                return JsonResponse({'message': str(exc)}, status=exc.status)
            if exc.status == 404:
                raise Http404('File not found.')
            return render(request, 'dwiest-django-demos/file/error.html', {'storage_error': str(exc)}, status=exc.status)
    return wrapped


def present(item):
    return dict(item, path=item['file_id'], ready=item['status'] == 'ready',
                created_at=datetime.fromtimestamp(int(item['created_at']), timezone.utc))


def details_url(file_id):
    return reverse('demos:file:details') + '?' + urlencode({'path': file_id})


@access
@require_GET
def index(request):
    store = FileStore(request.user.pk)
    cursor = None
    if request.GET.get('cursor'):
        try:
            data = signing.loads(request.GET['cursor'], salt='file-manager-cursor', max_age=86400)
            if data['owner'] != request.user.pk:
                raise ValueError()
            cursor = data['file_id']
        except (signing.BadSignature, KeyError, ValueError, TypeError):
            raise StorageError('Invalid file list page. Return to All files.', 400)
    files, next_id = store.listing(cursor)
    next_cursor = signing.dumps({'owner': request.user.pk, 'file_id': next_id}, salt='file-manager-cursor') if next_id else None
    return render(request, 'dwiest-django-demos/file/index.html', {
        'files': [present(item) for item in files], 'summary': store.summary(), 'quota': store.quota(),
        'next_cursor': next_cursor})


@access
@require_POST
def register(request):
    try:
        if len(request.body) > 16384:
            raise ValueError()
        payload = json.loads(request.body.decode('utf-8'))
        if not isinstance(payload, dict):
            raise ValueError()
    except (ValueError, UnicodeError):
        raise StorageError('Supply valid upload details.', 400)
    result = FileStore(request.user.pk).register(payload, request.META.get('HTTP_IDEMPOTENCY_KEY'))
    response = {'file': {'file_id': result['file']['file_id']}}
    if 'upload' in result:
        response['upload'] = result['upload']
    return JsonResponse(response)


@access
@require_POST
def complete(request, file_id):
    item = FileStore(request.user.pk).complete(file_id)
    return JsonResponse({'detail_url': details_url(item['file_id'])})


@access
@require_http_methods(['GET', 'POST'])
def details(request):
    file_id = request.POST.get('path') if request.method == 'POST' else request.GET.get('path')
    store = FileStore(request.user.pk)
    item = store.get(file_id)
    form = FileDetailsForm(request.POST if request.method == 'POST' else None, initial=item)
    if request.method == 'POST' and form.is_valid():
        store.update(file_id, **form.cleaned_data)
        file_updated.send(sender=request.user.__class__, request=request, id=file_id, name=form.cleaned_data['name'])
        messages.success(request, 'File details saved.')
        return redirect(details_url(file_id))
    return render(request, 'dwiest-django-demos/file/details.html', {'file': present(item), 'form': form})


@access
@require_http_methods(['GET', 'POST'])
def delete(request):
    file_id = request.POST.get('path') if request.method == 'POST' else request.GET.get('path')
    store = FileStore(request.user.pk)
    item = store.get(file_id)
    if request.method == 'POST':
        store.delete(file_id)
        file_deleted.send(sender=request.user.__class__, request=request, id=file_id, name=item['name'])
        messages.success(request, 'File deleted. Stored copies will be removed by scheduled cleanup.')
        return redirect('demos:file:index')
    return render(request, 'dwiest-django-demos/file/delete.html', {'file': present(item)})


@access
@require_GET
def download(request):
    return HttpResponseRedirect(FileStore(request.user.pk).download(request.GET.get('path')))


@access
@require_GET
def open_file(request):
    return HttpResponseRedirect(FileStore(request.user.pk).download(request.GET.get('path'), inline=True))
