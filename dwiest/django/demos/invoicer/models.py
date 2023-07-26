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


class Address(BaseModel, OwnedModel, NamedModel, models.Model):
  class Meta:
    abstract = True
#    ordering = ['-created_at', '-id']

  line_1 = models.CharField(max_length=255)
  line_2 = models.CharField(max_length=255)
  city = models.CharField(max_length=255)
  state = models.CharField(max_length=255)
  zipcode = models.CharField(max_length=10)
  #province = models.ChoiceField()
  #country = models.ChoiceField()


class BillTo(Address):
  def __init__(self, *args, **kwargs):
    print("BillTo.__init__()")
    print(kwargs)
    super().__init__(*args, **kwargs)

  def __str__(self):
    return self.name


class Invoice(BaseModel, OwnedModel, NamedModel):

  bill_to = models.ForeignKey(
    BillTo,
    on_delete=models.CASCADE,
    blank = True,
    null = True,
    )

  invoice_date = models.DateField(
    #auto_now_add=True, #doesn't show on form
    editable=True,
    )


  def total(self):
    if not hasattr(self,'_total'):
      print("{}.total(): not cached".format(self.__class__.__name__))
      amount = 0
      items = []
      try:
        items = LineItem.objects.filter(owner=49,invoice=1)
      except Exception as e:
        print(e)
      for item in items:
        print("amount: {}".format(item.total()))
        amount += item.total()
      self._total = amount
    else:
      print("{}.total(): cached".format(self.__class__.__name__))

    print("total: {}".format(self._total))
    return self._total


  def due_date(self):
    terms = 30
    if hasattr(self,'_due_date') == False:
      time_delta = timedelta(days=terms)
      self._due_date = self.invoice_date + time_delta

    print("{}.terms {}".format(self.__class__.__name__, terms))
    print("{}.invoice_date {}".format(self.__class__.__name__, self.invoice_date))
    print("{}.due_date {}".format(self.__class__.__name__, self._due_date))
    return self._due_date

  def terms(self):
    print("TERMS: NET30")
    return 'NET30'


class LineItem(BaseModel, OwnedModel):
  class Meta:
    ordering = ['date']

  invoice = models.ForeignKey(
    Invoice,
    on_delete=models.CASCADE,
    blank = False,
    null = False,
    )

  date = models.DateField(
    #auto_now_add=True, # doesn't show on form
    #blank = True,
    #null = True,
    editable=True,
    )

  description = models.CharField(max_length=255)
  rate = models.IntegerField(default=80)

  quantity = models.DecimalField(
    default        = 1,
    max_digits     = 4,
    decimal_places = 2
    )

  def total(self):
    return self.quantity * self.rate



class Address(BaseModel, OwnedModel, NamedModel, models.Model):
  class Meta:
    abstract = True
#    ordering = ['-created_at', '-id']

  line_1 = models.CharField(max_length=255)
  line_2 = models.CharField(max_length=255)
  city = models.CharField(max_length=255)
  state = models.CharField(max_length=255)
