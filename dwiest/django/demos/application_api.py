from rest_framework.permissions import BasePermission
from rest_framework.views import APIView
from .application_access import for_request


class ApplicationPermission(BasePermission):
    message = 'You do not have access to this application.'

    def has_permission(self, request, view):
        return for_request(request).allows(view.application_key)


class BookmarkAPIView(APIView):
    application_key = 'bookmarks'
    permission_classes = tuple(APIView.permission_classes) + (ApplicationPermission,)
