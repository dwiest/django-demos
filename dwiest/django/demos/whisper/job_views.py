from datetime import datetime, timezone
from urllib.parse import urlencode
from uuid import uuid4

from django.contrib import messages
from django.http import Http404, JsonResponse
from django.shortcuts import render, redirect
from django.views.decorators.http import require_GET

from .client import WhisperClient, ServiceError
from .forms import TranscriptionForm
from .views import access, present

TERMINAL = ('completed', 'failed', 'cancelled')


def job_present(item):
    item = dict(item)
    start = item.get('started_at')
    end = item.get('completed_at') or datetime.now(timezone.utc).timestamp()
    item['elapsed_seconds'] = max(0, end - start) if start is not None else None
    item['queue_seconds'] = max(0, (start or end) - item['created_at'])
    summary = item.get('summary') or {}
    item['recording_seconds'] = summary.get('audio_duration_seconds')
    item['is_analysis'] = item.get('type')=='transcript.analyze'
    item['can_analyze'] = item['status']=='completed' and not item['is_analysis']
    item['can_review'] = item['is_analysis'] and item.get('review_status')=='pending' and item['status']=='completed'
    item['terminal'] = item['status'] in TERMINAL
    item['cancellable'] = item['status'] in ('queued', 'running')
    item['can_delete'] = item['terminal']
    for field in ('created_at', 'started_at', 'updated_at', 'completed_at', 'expires_at'):
        if item.get(field) is not None:
            item[field + '_date'] = datetime.fromtimestamp(item[field], timezone.utc)
    return item


def error(request, exc):
    if exc.status == 404:
        raise Http404('Job or file not found.')
    return render(request, 'dwiest-django-demos/whisper/error.html', {'service_error': str(exc)}, status=exc.status)


@access
def transcribe(request, file_id):
    if request.method not in ('GET', 'POST'):
        from django.http import HttpResponseNotAllowed
        return HttpResponseNotAllowed(['GET', 'POST'])
    try:
        client = WhisperClient(request.user)
        file = present(client.request('GET', '/files/' + file_id)['file'])
        if not file['ready']:
            raise ServiceError('This file is not available for transcription.', 409)
        form = TranscriptionForm(request.POST if request.method == 'POST' else None,
                                 initial={'operation_key': uuid4().hex})
        service_error = None
        if request.method == 'POST' and form.is_valid():
            try:
                result = client.request('POST', '/jobs', form.payload(file_id), form.cleaned_data['operation_key'])
                return redirect('demos:whisper:job', job_id=result['job']['job_id'])
            except ServiceError as exc:
                # Preserve the operation key and options after uncertain submissions.
                service_error = str(exc)
        return render(request, 'dwiest-django-demos/whisper/transcribe.html',
                      {'file': file, 'form': form, 'service_error': service_error})
    except ServiceError as exc:
        return error(request, exc)


@access
@require_GET
def history(request, file_id=None):
    try:
        client = WhisperClient(request.user)
        path = '/files/' + file_id + '/jobs' if file_id else '/jobs'
        cursor = request.GET.get('cursor')
        if cursor:
            path += '?' + urlencode({'cursor': cursor})
        result = client.request('GET', path)
        return render(request, 'dwiest-django-demos/whisper/jobs.html',
            {'jobs': [job_present(item) for item in result['jobs']], 'next_cursor': result.get('next_cursor'), 'file_id': file_id})
    except ServiceError as exc:
        return error(request, exc)


@access
@require_GET
def detail(request, job_id):
    try:
        client = WhisperClient(request.user)
        job = job_present(client.request('GET', '/jobs/' + job_id)['job'])
        result = client.request('GET', '/jobs/' + job_id + '/result') if job['status'] == 'completed' else None
        return render(request, 'dwiest-django-demos/whisper/job.html', {'job': job, 'result': result, 'analysis_display':job.get('approved_proposal') or (result or {}).get('proposal')})
    except ServiceError as exc:
        return error(request, exc)


@access
@require_GET
def status(request, job_id):
    try:
        result = WhisperClient(request.user).request('GET', '/jobs/' + job_id)
        # No transcripts, credentials, source keys or signed URLs in status polling.
        return JsonResponse({'job': result['job']})
    except ServiceError as exc:
        return JsonResponse({'message': str(exc)}, status=exc.status)


@access
def action(request, job_id, action):
    if request.method not in ('GET', 'POST'):
        from django.http import HttpResponseNotAllowed
        return HttpResponseNotAllowed(['GET', 'POST'])
    try:
        client = WhisperClient(request.user)
        job = job_present(client.request('GET', '/jobs/' + job_id)['job'])
        if request.method == 'POST':
            if action == 'cancel':
                client.request('POST', '/jobs/' + job_id + '/cancel', {})
                messages.success(request, 'Cancellation requested. A running worker stops at its next heartbeat.')
                return redirect('demos:whisper:job', job_id=job_id)
            client.request('DELETE', '/jobs/' + job_id)
            messages.success(request, 'Job deletion requested. Cleanup will remove its outputs and release the recording dependency.')
            return redirect('demos:whisper:jobs')
        return render(request, 'dwiest-django-demos/whisper/job_action.html', {'job': job, 'action': action})
    except ServiceError as exc:
        return error(request, exc)
