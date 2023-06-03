from django.contrib.auth.models import User
from django.db import models


class NewsItem(models.Model):
  class Meta:
    ordering = ['-created_at', '-id']

  owner = models.ForeignKey(
    User,
    on_delete=models.PROTECT,
    blank = True,
    null = True,
    )

  name = models.CharField(
    max_length=255,
    unique=True,
    )

  description = models.TextField(
    blank=True,
    null=True,
    )

  content = models.TextField(
    blank=True,
    null=True,
    )

  created_at = models.DateTimeField(
    auto_now_add=True,
    editable=False,
    )

  last_modified = models.DateTimeField(
    auto_now=True,
    editable=False,
    )

  begin_time = models.DateTimeField(
    editable=True,
    )

  end_time = models.DateTimeField(
    null=True,
    auto_now=False,
    editable=True,
    )

  status = models.IntegerField(
    default=0,
    )

  id = -1
