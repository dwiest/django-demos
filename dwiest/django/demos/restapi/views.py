from django.contrib.auth.models import Group, User, Permission
from rest_framework import permissions, viewsets

from dwiest.django.demos.restapi.serializers import BookmarkSerializer, GroupSerializer, UserSerializer
from dwiest.django.demos.bookmarks.models import Bookmark
from ..application_api import ApplicationPermission


class ModelPermissions(permissions.DjangoModelPermissions):
    perms_map = dict(permissions.DjangoModelPermissions.perms_map,
                     GET=['%(app_label)s.view_%(model_name)s'],
                     HEAD=['%(app_label)s.view_%(model_name)s'])


class ApplicationAdminAPI:
    application_key = 'restapi'
    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser, ApplicationPermission, ModelPermissions]

class UserViewSet(ApplicationAdminAPI, viewsets.ModelViewSet):
    """
    API endpoint that allows users to be viewed or edited.
    """
    queryset = User.objects.all().order_by('-date_joined')
    serializer_class = UserSerializer


class GroupViewSet(ApplicationAdminAPI, viewsets.ModelViewSet):
    """
    API endpoint that allows groups to be viewed or edited.
    """
    queryset = Group.objects.all().order_by('name')
    serializer_class = GroupSerializer


class BookmarkViewSet(ApplicationAdminAPI, viewsets.ModelViewSet):
    """
    API endpoint that allows groups to be viewed or edited.
    """
    queryset = Bookmark.objects.all().order_by('id')
    serializer_class = BookmarkSerializer

