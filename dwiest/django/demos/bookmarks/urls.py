from django.urls import path
from .views import (
    BookmarksView, QuickAddBookmarkView, BookmarkView, BookmarkExportView,
    TagsView, TagFormView, TagView, BookmarkTagFormView,
)
from .api_views import (
    BookmarkCreateAPIView, BookmarkLookupAPIView, BookmarkDetailAPIView,
    TagListAPIView, TagDetailAPIView, BookmarkTagListAPIView,
    BookmarkTagDetailAPIView,
)

from .ui_views import BookmarkPermanentDeleteUI, BookmarksUI, BookmarkEditorUI, BookmarkActionUI, TagsUI, TagEditorUI, LegacyTagRedirectUI, LegacyBookmarkTagRedirectUI
from .ai_views import AISettingsView, AIReviewView
from .enrichment_views import EnrichmentView
from .history_views import EnrichmentHistoryView

from .pwa_urls import urlpatterns as pwa_patterns

app_name = "bookmarks"

urlpatterns = [
    path('enrichment/history/', EnrichmentHistoryView.as_view(), name='enrichment_history'),
    path('enrichment/<uuid:attempt_id>/', EnrichmentView.as_view(), name='enrichment'),
    path('ai/settings/', AISettingsView.as_view(), name='ai_settings'),
    path('ai/review/<uuid:analysis_id>/', AIReviewView.as_view(), name='ai_review'),
    path("bookmark/<int:bookmark_id>/permanent-delete/", BookmarkPermanentDeleteUI.as_view(), name="ui_permanent_delete"),
    path("bookmark/<int:bookmark_id>/action/", BookmarkActionUI.as_view(), name="ui_action"),
    path("", BookmarksUI.as_view(), name="home"),
    path("add", QuickAddBookmarkView.as_view(), name="add"),
    path("bookmark", BookmarkEditorUI.as_view(), name="bookmark"),
    path("export", BookmarkExportView.as_view(), name="export"),
    path("tags", TagsUI.as_view(), name="tags"),
    path("tags/edit", TagEditorUI.as_view(), name="tag_edit"),
    path("tags/create", TagEditorUI.as_view(), name="tag_create"),
    path("tags/view", LegacyTagRedirectUI.as_view(), name="tag_view"),
    path("tag", LegacyBookmarkTagRedirectUI.as_view(), name="tag"),
    path("api/bookmarks/lookup/", BookmarkLookupAPIView.as_view(), name="api_bookmark_lookup"),
    path("api/bookmarks/", BookmarkCreateAPIView.as_view(), name="api_bookmark_create"),
    path("api/bookmarks/<int:bookmark_id>/", BookmarkDetailAPIView.as_view(), name="api_bookmark_detail"),
    path("api/bookmarks/<int:bookmark_id>/tags/", BookmarkTagListAPIView.as_view(), name="api_bookmark_tags"),
    path("api/bookmarks/<int:bookmark_id>/tags/<int:tag_id>/", BookmarkTagDetailAPIView.as_view(), name="api_bookmark_tag_detail"),
    path("api/tags/", TagListAPIView.as_view(), name="api_tag_list"),
    path("api/tags/<int:tag_id>/", TagDetailAPIView.as_view(), name="api_tag_detail"),
]

urlpatterns += pwa_patterns
