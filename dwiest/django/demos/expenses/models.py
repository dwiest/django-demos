from django.contrib.auth.models import User
from django.db import models
from datetime import timedelta

class BaseModel(models.Model):
  class Meta:
    abstract = True

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


class OwnedModel(models.Model):
  class Meta:
    abstract = True

  owner = models.ForeignKey(
    User,
    on_delete=models.PROTECT,
    blank = True,
    null = True,
    )


class NamedModel(models.Model):
  class Meta:
    abstract = True

  name = models.CharField(
    max_length=255,
    unique=True,
    )

  description = models.CharField(max_length=255)


class ExpenseList(OwnedModel, NamedModel):
  pass


class ExpenseCategory(OwnedModel, NamedModel):
  code = models.CharField(
    max_length=255,
    unique=True,
    )


class Expense(OwnedModel, NamedModel):
  list = models.ForeignKey(
    ExpenseList,
    on_delete=models.PROTECT,
    null = False,
    )

  category = models.ForeignKey(
    ExpenseCategory,
    on_delete=models.PROTECT,
    null = False,
    )

  amount = models.FloatField(
    null = False,
    )


