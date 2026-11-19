from uuid import uuid4
from django.contrib import messages
from django.shortcuts import render, redirect
from django.views.decorators.http import require_http_methods
from .views import access
from .job_views import error, job_present
from .client import WhisperClient, ServiceError
from .forms import AnalysisForm, AnalysisReviewForm


@access
@require_http_methods(['GET','POST'])
def submit(request,job_id):
    try:
        client=WhisperClient(request.user)
        source=client.request('GET','/jobs/'+job_id)['job']
        form=AnalysisForm(request.POST if request.method=='POST' else None,initial={'operation_key':uuid4().hex})
        service_error=None
        if source['status']!='completed' or source.get('type','media.transcribe')!='media.transcribe':
            raise ServiceError('Choose a completed transcription.',409)
        if request.method=='POST' and form.is_valid():
            try:
                result=client.request('POST','/jobs/'+job_id+'/analyze',
                    {k:form.cleaned_data[k] for k in ('instructions','retention_days')},form.cleaned_data['operation_key'])
                return redirect('demos:whisper:job',job_id=result['job']['job_id'])
            except ServiceError as exc:service_error=str(exc)
        return render(request,'dwiest-django-demos/whisper/analyze.html',{'source':source,'form':form,'service_error':service_error})
    except ServiceError as exc:return error(request,exc)


@access
@require_http_methods(['GET','POST'])
def review(request,job_id):
    try:
        client=WhisperClient(request.user)
        result=client.request('GET','/jobs/'+job_id+'/result')
        job=job_present(result['job'])
        if not job['is_analysis']:raise ServiceError('This job is not an analysis.',409)
        initial={k:'\n'.join(v) if isinstance(v,list) else v for k,v in result['proposal'].items()}
        form=AnalysisReviewForm(request.POST if request.method=='POST' else None,initial=initial)
        if request.method=='POST':
            if request.POST.get('action')=='reject':
                client.request('POST','/jobs/'+job_id+'/review',{'action':'reject'})
                messages.success(request,'Analysis rejected. The transcript is unchanged.')
                return redirect('demos:whisper:job',job_id=job_id)
            if form.is_valid():
                client.request('POST','/jobs/'+job_id+'/review',{'action':'approve','proposal':form.cleaned_data})
                messages.success(request,'Approved analysis saved. No additional OpenAI call was made.')
                return redirect('demos:whisper:job',job_id=job_id)
        return render(request,'dwiest-django-demos/whisper/analysis_review.html',{'job':job,'form':form})
    except ServiceError as exc:return error(request,exc)
