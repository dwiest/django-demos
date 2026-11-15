"""AI preferences and expiring review records; credentials are always ciphertext."""
import uuid
from django.conf import settings
from django.db import models


class BookmarkAISettings(models.Model):
    owner = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    encrypted_api_key = models.TextField(blank=True, default='')
    instructions = models.TextField(blank=True, default='')
    model = models.CharField(max_length=100, blank=True, default='')
    blocked_domains = models.JSONField(default=list, blank=True)


class BookmarkAIAnalysis(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    bookmark_id = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    original = models.JSONField(default=dict)
    proposal = models.JSONField(default=dict)
    sources = models.JSONField(default=list)
    # CAS pending -> applying prevents duplicate browser submissions. Any ambiguous
    # execution stays uncertain and cannot be retried automatically.
    status = models.CharField(max_length=16, default='pending')
    approved = models.JSONField(default=dict)
    results = models.JSONField(default=list)
