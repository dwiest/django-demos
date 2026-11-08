from django.urls import path
from .pwa_views import CaptureView, manifest, service_worker

# Include inside the existing bookmarks URLconf, without a second namespace.
urlpatterns = [
    path('capture/', CaptureView.as_view(), name='capture'),
    path('manifest.webmanifest', manifest, name='pwa_manifest'),
    path('sw.js', service_worker, name='pwa_worker'),
]
