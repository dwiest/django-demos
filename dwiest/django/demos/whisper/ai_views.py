from django.contrib import messages
from django.shortcuts import render, redirect
from django.views.decorators.debug import sensitive_post_parameters, sensitive_variables
from django.views.decorators.http import require_http_methods

from .views import access
from .client import WhisperClient, ServiceError
from .forms import AISettingsForm


@access
@require_http_methods(['GET', 'POST'])
@sensitive_post_parameters('api_key')
@sensitive_variables()
def settings(request):
    error = None
    has_key = False
    try:
        client = WhisperClient(request.user)
        current = client.request('GET', '/ai/settings')
        has_key = current['has_api_key']
        form = AISettingsForm(request.POST if request.method == 'POST' else None, initial={
            'model': current['model'], 'instructions': current['instructions']})
        if request.method == 'POST' and form.is_valid():
            client.request('POST', '/ai/settings', form.cleaned_data)
            messages.success(request, 'AI settings saved. No analysis request was made.')
            return redirect('demos:whisper:ai_settings')
    except ServiceError as exc:
        error = str(exc)
        form = AISettingsForm(request.POST if request.method == 'POST' else None)
    return render(request, 'dwiest-django-demos/whisper/ai_settings.html',
        {'form': form, 'has_api_key': has_key, 'service_error': error})
