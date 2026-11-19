from django.urls import path
from . import views

app_name = 'whisper'
urlpatterns = [
    path('', views.home, name='home'),
    path('upload/', views.upload, name='upload'),
    path('uploads/register/', views.register_upload, name='register'),
    path('files/<slug:file_id>/', views.detail, name='detail'),
    path('files/<slug:file_id>/complete/', views.complete, name='complete'),
    path('files/<slug:file_id>/download/', views.download, name='download'),
    path('files/<slug:file_id>/delete/', views.delete, name='delete'),
]
