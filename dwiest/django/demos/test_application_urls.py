from django.contrib import admin
from django.http import HttpResponse
from django.urls import include, path
from django.views.generic import TemplateView
from rest_framework.authentication import BasicAuthentication, SessionAuthentication
from rest_framework.response import Response

from .application_api import BookmarkAPIView
from .application_views import desktop_toys
from .inventory.api_views import ItemListAPI
from .bookmarks.batch_api import BulkLookupAPIView
from .bookmarks.api_views import BookmarkLookupAPIView
from .restapi.views import GroupViewSet, UserViewSet


def page(request):
    return HttpResponse('Application page')


class ProbeAPI(BookmarkAPIView):
    authentication_classes = [BasicAuthentication, SessionAuthentication]

    def get(self, request):
        return Response({'user': request.user.username})

    def post(self, request):
        return self.get(request)


demos = [
    path('', TemplateView.as_view(template_name='dwiest-django-demos/demo_landing.html'), name='home'),
    path('toys/', desktop_toys, name='desktop_toys'),
]
for key in ['bookmarks', 'invoicer', 'journal', 'qrcode', 'otp', 'expenses',
            'inventory', 'file', 'news', 'selenium', 'store', 'grecaptcha']:
    routes = [path('', page, name='home'), path('index/', page, name='index'), path('child/', page, name='child')]
    if key == 'bookmarks':
        routes += [path('api/', ProbeAPI.as_view(), name='probe_api'),
                   path('lookup/', BookmarkLookupAPIView.as_view(), name='lookup'),
                   path('bulk/', BulkLookupAPIView.as_view(), name='bulk_lookup')]
    if key == 'inventory':
        routes += [path('api/items/', ItemListAPI.as_view(), name='api_items')]
    demos.append(path(key + '/', include((routes, key), namespace=key)))
demos.append(path('whisper/', include('dwiest.django.demos.whisper.urls', namespace='whisper')))
demos.append(path('new-app/', include(([path('', page, name='home')], 'new_app'), namespace='new_app')))
demos.append(path('restapi/', include(([
    path('users/', UserViewSet.as_view({'get': 'list', 'post': 'create'}), name='user-list'),
    path('users/<int:pk>/', UserViewSet.as_view({'get': 'retrieve'}), name='user-detail'),
    path('groups/<int:pk>/', GroupViewSet.as_view({'get': 'retrieve'}), name='group-detail'),
], 'restapi'), namespace='restapi')))

urlpatterns = [
    path('apps/demos/', include((demos, 'demos'), namespace='demos')),
    path('login/', page, name='login'),
    path('apps/status/', page, name='status'),
    path('desktop-toys/fireworks/index.html', page, name='toy_external'),
    path('admin/', admin.site.urls),
]
