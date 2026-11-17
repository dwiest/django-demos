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
    download_on_create = models.BooleanField(default=False)
    enrich_on_create = models.BooleanField(default=False)
    failed_attempt_retention_days = models.PositiveIntegerField(default=30, null=True, blank=True)
    use_job_service = models.BooleanField(default=False)
    include_raw_html = models.BooleanField(default=True)
    job_retention_days = models.PositiveIntegerField(default=365, null=True, blank=True)


class BookmarkAIAttempt(models.Model):
    """Latest attempted analysis per account/URL, including unsuccessful requests."""
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    url = models.CharField(max_length=255)
    last_attempted_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = (('owner', 'url'),)


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


class BookmarkEnrichmentAttempt(models.Model):
    """Durable orchestration; remote artifacts stay owned by the job service."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    bookmark_id = models.PositiveIntegerField(null=True, db_index=True)
    fingerprint = models.CharField(max_length=64)
    url = models.URLField(max_length=255)
    service_url = models.URLField(max_length=500)
    status = models.CharField(max_length=32, default='retrieval_pending')
    mode = models.CharField(max_length=16, default='analyze')
    request_options = models.JSONField(default=dict)
    original = models.JSONField(default=dict)
    retrieval_job_id = models.CharField(max_length=32, blank=True, default='')
    analysis_job_id = models.CharField(max_length=32, blank=True, default='')
    retrieval = models.JSONField(default=dict)
    analysis = models.JSONField(default=dict)
    error = models.JSONField(default=dict)
    review = models.ForeignKey(BookmarkAIAnalysis, null=True, blank=True, on_delete=models.SET_NULL)
    lease_token = models.CharField(max_length=32, blank=True, default='')
    lease_until = models.DateTimeField(null=True, blank=True)
    retry_after = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def bookmark(self):
        from .bookmarks.models import Bookmark
        return Bookmark.objects.filter(pk=self.bookmark_id, owner=self.owner).first()

    class Meta:
        unique_together = (('owner', 'fingerprint'),)
        ordering = ['-created_at']
