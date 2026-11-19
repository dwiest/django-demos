from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.views.decorators.debug import sensitive_post_parameters, sensitive_variables
from django.views.decorators.http import require_http_methods

from .views import access
from .client import WhisperClient, ServiceError
from .forms import AISettingsForm
from .analysis_defaults import DEFAULT_INSTRUCTIONS


@access
@require_http_methods(['GET', 'POST'])
@sensitive_post_parameters('api_key')
@sensitive_variables()
def settings(request):
    error = None
    has_key = False
    test_message = None
    try:
        client = WhisperClient(request.user)
        current = client.request('GET', '/ai/settings')
        has_key = current['has_api_key']
        form = AISettingsForm(request.POST if request.method == 'POST' else None, initial={
            'model': current['model'], 'instructions': current['instructions'] or DEFAULT_INSTRUCTIONS})
        if request.method == 'POST' and form.is_valid():
            if request.POST.get('action') == 'test':
                if form.cleaned_data['remove_api_key']:
                    form.add_error('remove_api_key','Uncheck Remove before testing.')
                else:
                    result=client.request('POST','/ai/test',{'model':form.cleaned_data['model'],'api_key':form.cleaned_data['api_key']})
                    test_message=result['message']
                    if 'application/json' in request.META.get('HTTP_ACCEPT',''):
                        return JsonResponse({'message':test_message})
            else:
                client.request('POST', '/ai/settings', {k:form.cleaned_data[k] for k in ('model','instructions','api_key','remove_api_key')})
                messages.success(request, 'AI settings saved. No analysis request was made.')
                return redirect('demos:whisper:ai_settings')
    except ServiceError as exc:
        if request.POST.get('action')=='test' and 'application/json' in request.META.get('HTTP_ACCEPT',''):
            return JsonResponse({'message':str(exc)},status=exc.status)
        error = str(exc)
        form = AISettingsForm(request.POST if request.method == 'POST' else None)
    if request.POST.get('action')=='test' and 'application/json' in request.META.get('HTTP_ACCEPT',''):
        return JsonResponse({'message':'Correct the settings fields before testing.'},status=400)
    return render(request, 'dwiest-django-demos/whisper/ai_settings.html',
        {'form': form, 'has_api_key': has_key, 'service_error': error, 'test_message':test_message,'default_instructions':DEFAULT_INSTRUCTIONS})
