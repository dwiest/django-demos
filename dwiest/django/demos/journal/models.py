from django.contrib.auth.models import User
from django.db import models


class Journal(models.Model):
  class Meta:
    ordering = ['id']

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

  created_at = models.DateTimeField(
    auto_now_add=True,
    editable=False,
    )

  last_modified = models.DateTimeField(
    auto_now=True,
    editable=False,
    )

  status = models.IntegerField(
    default=0,
    )


class JournalEntry(models.Model):
  class Meta:
    ordering = ['-date', '-id']

  owner = models.ForeignKey(
    User,
    on_delete=models.PROTECT,
    blank = True,
    null = True,
    )

  journal = models.ForeignKey(
    Journal,
    on_delete=models.CASCADE,
    blank = True,
    null = True,
    )

  content = models.TextField(
    blank=True,
    null=True,
    )

  created_at = models.DateTimeField(
    auto_now_add=True,
    editable=False,
    )

  date = models.DateTimeField(
    auto_now=False,
    editable=True,
    )

  last_modified = models.DateTimeField(
    auto_now=True,
    editable=False,
    )

  status = models.IntegerField(
    default=0,
    )
