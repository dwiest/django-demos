from django.contrib.auth.models import User
from django.db import models

class BillTo(models.Model):
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


class Invoice(models.Model):
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

  invoice_date = models.DateField(
    auto_now_add=True,
    editable=True,
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


class LineItem(models.Model):
  class Meta:
    ordering = ['-created_at', '-id']

  owner = models.ForeignKey(
    User,
    on_delete=models.PROTECT,
    blank = True,
    null = True,
    )

  date = models.DateField(
    auto_now_add=True,
    editable=True,
    )

  description = models.TextField(
    null=False,
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
