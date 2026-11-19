from django.urls import path
from . import views, job_views

app_name = 'whisper'
urlpatterns = [
    path('jobs/', job_views.history, name='jobs'),
    path('jobs/<slug:job_id>/', job_views.detail, name='job'),
    path('jobs/<slug:job_id>/status/', job_views.status, name='job_status'),
    path('jobs/<slug:job_id>/cancel/', job_views.action, {'action': 'cancel'}, name='job_cancel'),
    path('jobs/<slug:job_id>/delete/', job_views.action, {'action': 'delete'}, name='job_delete'),
    path('files/<slug:file_id>/transcribe/', job_views.transcribe, name='transcribe'),
    path('files/<slug:file_id>/jobs/', job_views.history, name='file_jobs'),
    path('', views.home, name='home'),
    path('upload/', views.upload, name='upload'),
    path('uploads/register/', views.register_upload, name='register'),
    path('files/<slug:file_id>/', views.detail, name='detail'),
    path('files/<slug:file_id>/complete/', views.complete, name='complete'),
    path('files/<slug:file_id>/download/', views.download, name='download'),
    path('files/<slug:file_id>/delete/', views.delete, name='delete'),
]
