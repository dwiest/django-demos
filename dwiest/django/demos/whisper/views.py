import json
from datetime import datetime, timezone
from functools import wraps
from urllib.parse import urlencode, urlsplit

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, JsonResponse, HttpResponseRedirect
from django.shortcuts import render, redirect
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.cache import never_cache

from ..application_access import for_request
from .client import WhisperClient, ServiceError
from .forms import FileForm


def access(view):
    @login_required
    @never_cache
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not for_request(request).allows('whisper'):
            return render(request, 'dwiest-django-demos/applications/denied.html', status=403)
        return view(request, *args, **kwargs)
    return wrapped


def present(item):
    item = dict(item)
    for field in ('created_at', 'ready_at', 'expires_at'):
        if item.get(field) is not None:
            item[field + '_date'] = datetime.fromtimestamp(item[field], timezone.utc)
    item['expired'] = item['status'] == 'ready' and item.get('expires_at') is not None and item['expires_at'] <= datetime.now(timezone.utc).timestamp()
    item['ready'] = item['status'] == 'ready' and (item.get('expires_at') is None or item['expires_at'] > datetime.now(timezone.utc).timestamp())
    return item


def detail_url(file_id):
    return reverse('demos:whisper:detail', args=[file_id])


@access
@require_GET
def home(request):
    context = {}
    try:
        cursor = request.GET.get('cursor', '')
        result = WhisperClient(request.user).request('GET', '/files' + ('?' + urlencode({'cursor': cursor}) if cursor else ''))
        context['files'] = [present(item) for item in result['files']]
        context['next_cursor'] = result.get('next_cursor')
    except ServiceError as exc:
        context['service_error'] = str(exc)
        return render(request, 'dwiest-django-demos/whisper/library.html', context, status=503)
    return render(request, 'dwiest-django-demos/whisper/library.html', context)


@access
@require_GET
def upload(request):
    return render(request, 'dwiest-django-demos/whisper/upload.html')


def json_payload(request):
    try:
        if len(request.body) > 16384:
            raise ValueError()
        value = json.loads(request.body.decode('utf-8'))
        if not isinstance(value, dict):
            raise ValueError()
        return value
    except (ValueError, UnicodeError):
        raise ServiceError('Supply valid upload details.', 400) from None


@access
@require_POST
def register_upload(request):
    try:
        result = WhisperClient(request.user).request('POST', '/files', json_payload(request), request.META.get('HTTP_IDEMPOTENCY_KEY'))
        result['detail_url'] = detail_url(result['file']['file_id'])
        return JsonResponse(result)
    except ServiceError as exc:
        return JsonResponse({'message': str(exc)}, status=exc.status)


@access
@require_POST
def complete(request, file_id):
    try:
        result = WhisperClient(request.user).request('POST', '/files/' + file_id + '/complete', {})
        result['detail_url'] = detail_url(file_id)
        return JsonResponse(result)
    except ServiceError as exc:
        return JsonResponse({'message': str(exc)}, status=exc.status)


@access
def detail(request, file_id):
    if request.method not in ('GET', 'POST'):
        from django.http import HttpResponseNotAllowed
        return HttpResponseNotAllowed(['GET', 'POST'])
    try:
        client = WhisperClient(request.user)
        item = client.request('GET', '/files/' + file_id)['file']
        form = FileForm(request.POST if request.method == 'POST' else None, initial={
            'display_name': item['display_name'], 'retention_days': item['retention_days'],
            'keep_indefinitely': item['retention_days'] is None})
        if request.method == 'POST' and form.is_valid():
            client.request('POST', '/files/' + file_id, {k: form.cleaned_data[k] for k in ('display_name', 'retention_days')})
            messages.success(request, 'File settings saved.')
            return redirect(detail_url(file_id))
        return render(request, 'dwiest-django-demos/whisper/detail.html', {'file': present(item), 'form': form})
    except ServiceError as exc:
        if exc.status == 404:
            raise Http404('File not found.')
        return render(request, 'dwiest-django-demos/whisper/error.html', {'service_error': str(exc)}, status=exc.status)


@access
@require_GET
def download(request, file_id):
    try:
        result = WhisperClient(request.user).request('GET', '/files/' + file_id + '/download')
        parsed = urlsplit(result['url'])
        if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
            raise ServiceError('The media service returned an invalid download URL.')
        return HttpResponseRedirect(result['url'])
    except ServiceError as exc:
        if exc.status == 404:
            raise Http404('File not found.')
        return render(request, 'dwiest-django-demos/whisper/error.html', {'service_error': str(exc)}, status=exc.status)


@access
def delete(request, file_id):
    if request.method not in ('GET', 'POST'):
        from django.http import HttpResponseNotAllowed
        return HttpResponseNotAllowed(['GET', 'POST'])
    try:
        client = WhisperClient(request.user)
        item = client.request('GET', '/files/' + file_id)['file']
        if request.method == 'POST':
            client.request('DELETE', '/files/' + file_id)
            messages.success(request, 'Deletion requested. The file is unavailable now; stored copies are removed by scheduled cleanup.')
            return redirect('demos:whisper:home')
        return render(request, 'dwiest-django-demos/whisper/delete.html', {'file': present(item)})
    except ServiceError as exc:
        if exc.status == 404:
            raise Http404('File not found.')
        return render(request, 'dwiest-django-demos/whisper/error.html', {'service_error': str(exc)}, status=exc.status)
