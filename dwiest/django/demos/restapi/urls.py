from django.urls import include, path
from rest_framework import routers

from dwiest.django.demos.restapi import views

app_name = "restapi" 

router = routers.DefaultRouter()
router.register(r'users', views.UserViewSet)
router.register(r'groups', views.GroupViewSet)
router.register(r'bookmarks', views.BookmarkViewSet)

# Wire up our API using automatic URL routing.
# Additionally, we include login URLs for the browsable API.
urlpatterns = [
    path('', include(router.urls)),
    path('api-auth/', include('rest_framework.urls', namespace='restapi'))
]
