from django.urls import path
from . import views

app_name = 'file'
urlpatterns = [
    path('', views.index, name='index'),
    path('details/', views.details, name='details'),
    path('delete/', views.delete, name='delete'),
    path('download/', views.download, name='download'),
    path('open/', views.open_file, name='open'),
    path('uploads/register/', views.register, name='register'),
    path('uploads/<str:file_id>/complete/', views.complete, name='complete'),
]
