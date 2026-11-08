from django.urls import path
from .batch_api import BulkLookupAPIView, BulkCreateAPIView, BulkUpdateAPIView

urlpatterns = [
    path("bookmarks/bulk-lookup/", BulkLookupAPIView.as_view(), name="api_bookmark_bulk_lookup"),
    path("bookmarks/bulk-create/", BulkCreateAPIView.as_view(), name="api_bookmark_bulk_create"),
    path("bookmarks/bulk-update/", BulkUpdateAPIView.as_view(), name="api_bookmark_bulk_update"),
]
