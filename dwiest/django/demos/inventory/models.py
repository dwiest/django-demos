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


class InventoryItem(BaseModel, OwnedModel, NamedModel):
  class Meta:
    abstract = False

  def __str__(self):
    return self.name



class InventoryList(BaseModel, OwnedModel, NamedModel):
  class Meta:
    ordering = ['last_modified']

  description = models.CharField(max_length=255)

  def __str__(self):
    return self.name



class InventoryEntry(BaseModel, OwnedModel):
  class Meta:
    ordering = ['date_added']

  item = models.ForeignKey(
    InventoryItem,
    on_delete=models.CASCADE,
    blank = False,
    null = False,
    )

  inventory_list = models.ForeignKey(
    InventoryList,
    on_delete=models.CASCADE,
    blank = False,
    null = False,
    )

  date_added = models.DateField(
    auto_now_add=True, # doesn't show on form
    #blank = True,
    #null = True,
    editable=False,
    )

  quantity = models.IntegerField(
    default = 1
    )

#  def inventory_list(self):
#    return self.inventory_list.name


class InventoryTransaction(models.Model):
  """Append-only application ledger; protect referenced entries from deletion."""
  entry = models.ForeignKey(InventoryEntry, on_delete=models.PROTECT, related_name='transactions')
  actor = models.ForeignKey(User, on_delete=models.PROTECT)
  operation = models.CharField(max_length=10)
  quantity = models.PositiveIntegerField()
  before = models.IntegerField()
  after = models.IntegerField()
  source = models.CharField(max_length=32, default='manual')
  reference_id = models.CharField(max_length=128, blank=True)
  metadata = models.JSONField(default=dict, blank=True)
  idempotency_key = models.CharField(max_length=128, null=True, blank=True)
  created_at = models.DateTimeField(auto_now_add=True)

  class Meta:
    ordering = ['-id']
    constraints = [models.UniqueConstraint(fields=['actor', 'idempotency_key'], name='inventory_actor_request_unique')]
