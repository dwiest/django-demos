from django.contrib.auth.models import User
from django.db import models
from datetime import datetime, timedelta
import re

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
  class Meta:
    ordering = ['-id']

  bill_to = models.ForeignKey(
    BillTo,
    on_delete=models.CASCADE,
    blank = True,
    null = True,
    )

  invoice_date = models.DateField(
    #auto_now_add=True, #doesn't show on form
    editable = True,
    null     = True
    )


  def hours(self):
    if not hasattr(self,'_hours'):
      print("{}.hours(): not cached".format(self.__class__.__name__))
      hours = 0.0
      items = []
      try:
        items = LineItem.objects.filter(owner=self.owner, invoice=self.id)
      except Exception as e:
        print(e)
      for item in items:
        print("hours: {}".format(item.quantity))
        hours += float(item.quantity)
      self._hours = hours
    else:
      print("{}.hours(): cached".format(self.__class__.__name__))

    print("hours: {}".format(self._hours))
    return self._hours


  def total(self):
    if not hasattr(self,'_total'):
      print("{}.total(): not cached".format(self.__class__.__name__))
      amount = 0
      items = []
      try:
        items = LineItem.objects.filter(owner=self.owner, invoice=self.id)
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
      if self.invoice_date != None:
        time_delta = timedelta(days=terms)
        self._due_date = self.invoice_date + time_delta
      else:
        self._due_date = "NOT ISSUED"

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
        blank=False,
        null=False,
    )

    date = models.DateField(editable=True)

    timeworked = models.CharField(
        max_length=75,
        null=True,
        blank=True,  # optional but recommended
    )

    description = models.TextField()

    rate = models.IntegerField(default=80)

    quantity = models.DecimalField(
        default=1,
        max_digits=4,
        decimal_places=2,
    )

    def total(self):
        return self.quantity * self.rate

    def calculate_decimal_hours(self):
        """
        Returns hours as a true decimal, e.g., 5.25 for 5 hours 15 minutes.
        """
        if not self.timeworked:
            return None

        first_line = self.timeworked.strip().splitlines()[0]
        timeworked = re.sub(r"\(.*?\)", "", first_line).strip()
        intervals = [i.strip() for i in timeworked.split(";")]
        total_minutes = 0

        for interval in intervals:
            if "->" not in interval:
                continue
            start_str, end_str = [x.strip() for x in interval.split("->")]
            try:
                start = datetime.strptime(start_str, "%H:%M")
                end = datetime.strptime(end_str, "%H:%M")
                diff = (end - start).total_seconds() / 60
                if diff < 0:
                    diff += 24 * 60  # handle overnight times
                total_minutes += int(diff)
            except ValueError:
                continue

        return round(total_minutes / 60, 2)

    def calculate_pseudo_hours(self):
        """
        Returns time in HH.MM format (e.g., 5.15 for 5h15m) — not true decimal.
        """
        if not self.timeworked:
            return ""

        first_line = self.timeworked.strip().splitlines()[0]
        timeworked = re.sub(r"\(.*?\)", "", first_line).strip()
        intervals = [i.strip() for i in timeworked.split(";")]
        total_minutes = 0

        for interval in intervals:
            if "->" not in interval:
                continue
            start_str, end_str = [x.strip() for x in interval.split("->")]
            try:
                start = datetime.strptime(start_str, "%H:%M")
                end = datetime.strptime(end_str, "%H:%M")
                diff = (end - start).total_seconds() / 60
                if diff < 0:
                    diff += 24 * 60  # handle overnight
                total_minutes += int(diff)
            except ValueError:
                continue

        hours = total_minutes // 60
        minutes = total_minutes % 60
        return f"{hours}.{minutes:02d}"


    def get_rolled_over_minutes(self):
        """
        Extracts rolled over minutes from timeworked string in format (.15),
        and returns as an integer number of minutes (e.g., 9 for .15).
        """
        if not self.timeworked:
            return 0

        first_line = self.timeworked.strip().splitlines()[0]
        match = re.search(r"\((?:0\.|\.)?(\d{1,2})\)", first_line)
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                return 0
        return 0


class Address(BaseModel, OwnedModel, NamedModel, models.Model):
  class Meta:
    abstract = True
#    ordering = ['-created_at', '-id']

  line_1 = models.CharField(max_length=255)
  line_2 = models.CharField(max_length=255)
  city = models.CharField(max_length=255)
  state = models.CharField(max_length=255)
