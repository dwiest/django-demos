"""Real store routes; unrelated demo destinations are placeholders for template tests."""
from django.http import HttpResponse
from django.urls import include, path
from django.views.generic import TemplateView

routes = [path('store/', include('dwiest.django.demos.store.urls')),
          path('', TemplateView.as_view(template_name='dwiest-django-demos/demo_landing.html'), name='home')]
for name in ['bookmarks', 'invoicer', 'journal', 'qrcode', 'otp', 'expenses',
             'inventory', 'file', 'news', 'selenium', 'grecaptcha']:
    routes.append(path(name+'/', include(([path('', lambda request: HttpResponse(''), name='home'),
                                         path('index/', lambda request: HttpResponse(''), name='index')], name), namespace=name)))
urlpatterns = [path('django/demos/', include((routes, 'demos'), namespace='demos'))]
