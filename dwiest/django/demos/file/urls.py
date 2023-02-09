"""users URL Configuration
The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.views.generic import TemplateView
from django.urls import path#, include
from .views import *

app_name = 'file'
urlpatterns = [
  path('',
    FileIndexView.as_view(),
    name='index'
    ),
  path('details/',
    FileDetailView.as_view(),
    name='details'
    ),
  path('delete/',
    FileDeleteView.as_view(),
    name='delete'
    ),
  path('download/',
    FileDownloadView.as_view(),
    name='download'
    ),
  path('open/',
    FileOpenView.as_view(),
    name='open'
    ),
]
