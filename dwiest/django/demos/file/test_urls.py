from django.urls import include, path
from ..test_application_urls import demos, urlpatterns as fixture_urls

routes = [route for route in demos if str(route.pattern) != 'file/']
routes.append(path('file/', include('dwiest.django.demos.file.urls', namespace='file')))
urlpatterns = [path('apps/demos/', include((routes, 'demos'), namespace='demos'))] + fixture_urls[1:]
