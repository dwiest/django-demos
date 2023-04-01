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
from django.contrib import admin
from django.urls import path, include
from django.views.generic.base import TemplateView

app_name='demos'
urlpatterns = [
  path('',
    TemplateView.as_view(
      template_name="dwiest-django-demos/home.html"), name='home'
    ),
  path('bookmarks/',
    include('dwiest.django.demos.bookmarks.urls', namespace='bookmarks')),
  path('file/',
    include('dwiest.django.demos.file.urls', namespace='file')),
  path('journal/',
    include('dwiest.django.demos.journal.urls', namespace='journal')),
  path('otp/',
    include('dwiest.django.demos.otp.urls', namespace='otp')),
  path('grecaptcha/',
    include('dwiest.django.demos.grecaptcha.urls', namespace='grecaptcha')),
  path('qrcode/',
    include('dwiest.django.demos.qrcode.urls', namespace='qrcode')),
  path('selenium/',
    include('dwiest.django.demos.selenium.urls', namespace='selenium')),
]
