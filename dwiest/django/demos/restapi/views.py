from django.contrib.auth.models import Group, User, Permission
from rest_framework import permissions, viewsets

from dwiest.django.demos.restapi.serializers import BookmarkSerializer, GroupSerializer, UserSerializer
from dwiest.django.demos.bookmarks.models import Bookmark

class UserViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows users to be viewed or edited.
    """
    queryset = User.objects.all().order_by('-date_joined')
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]


class GroupViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows groups to be viewed or edited.
    """
    queryset = Group.objects.all().order_by('name')
    serializer_class = GroupSerializer
    permission_classes = [permissions.IsAuthenticated]


class BookmarkViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows groups to be viewed or edited.
    """
    queryset = Bookmark.objects.all().order_by('id')
    serializer_class = BookmarkSerializer
    permission_classes = [permissions.IsAuthenticated]
