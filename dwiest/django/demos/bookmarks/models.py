from django.contrib.auth.models import User
from django.db import models


class Bookmark(models.Model):
  owner = models.ForeignKey(
    User,
    on_delete=models.PROTECT,
    blank = True,
    null = True,
    )

  url = models.CharField(
    max_length=255,
    )

  title = models.CharField(
    max_length=255,
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

  article_date = models.DateTimeField(
    blank=True,
    null=True,
    )

#class Screenshot(models.Model):
#  bookmark = models.ForeignKey(Bookmark)
#  path = models.TextField()
#  created_at = models.DateTimeField(auto_now_add=True)

#class Label(models.Model):
#  name = models.CharField(max_length=255)
#  description = models.TextField(blank=True, null=True)
#  bookmark = models.ManyToMany(Bookmark)
