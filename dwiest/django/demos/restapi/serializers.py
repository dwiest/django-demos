from django.contrib.auth.models import Group, User
from rest_framework import serializers
from dwiest.django.demos.bookmarks.models import Bookmark


class UserSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name="demos:restapi:user-detail")
    groups = serializers.HyperlinkedIdentityField(view_name="demos:restapi:group-detail")

    class Meta:
        model = User
        fields = ['url', 'username', 'email', 'groups']


class GroupSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name="demos:restapi:group-detail")

    class Meta:
        model = Group
        fields = ['url', 'name']


class BookmarkSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name="demos:restapi:bookmark-detail")
    owner = serializers.HyperlinkedIdentityField(view_name="demos:restapi:user-detail")

    class Meta:
        model = Bookmark
        #fields = ['url', 'title']
        fields = '__all__'
