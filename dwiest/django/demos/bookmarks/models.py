from django.contrib.auth.models import User
from django.db import models


class Bookmark(models.Model):
  class Meta:
    ordering = ['-article_date', '-id']

  owner = models.ForeignKey(
    User,
    on_delete=models.PROTECT,
    blank = True,
    null = True,
    )

  url = models.CharField(
    max_length=255,
    unique=True,
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

  '''
    article_date should be a DateField, but this causes problems
    with SQLite as a backend since the value it returns includes a time.

    return Database.Cursor.execute(self, query, params)
      File "/usr/lib64/python3.7/sqlite3/dbapi2.py", line 64, in convert_date
          return datetime.date(*map(int, val.split(b"-")))
          ValueError: invalid literal for int() with base 10: b'05 00:00:00'
  '''
  article_date = models.DateTimeField(
    blank=True,
    null=True,
    )

  status = models.IntegerField(
    default=0,
    )

  unread = models.BooleanField(
    default=False,
    )

  def __str__(self):
    if self.title:
      return self.title
    else:
      return self.url

  def tags(self):
    tags = []
    bookmark_tags = BookmarkTag.objects.filter(owner=self.owner, bookmark_id=self.id)
    for item in bookmark_tags:
      tag = Tag.objects.get(owner=item.owner, id=item.tag_id)
      tags.append(tag)
    return tags


#class Screenshot(models.Model):
#  bookmark = models.ForeignKey(Bookmark)
#  path = models.TextField()
#  created_at = models.DateTimeField(auto_now_add=True)

#class Label(models.Model):
#  name = models.CharField(max_length=255)
#  description = models.TextField(blank=True, null=True)
#  bookmark = models.ManyToMany(Bookmark)

class Tag(models.Model):
  class Meta:
    ordering = ['-id']

  created_at = models.DateTimeField(
    auto_now_add=True,
    editable=False,
    null = True,
    )

  last_modified = models.DateTimeField(
    auto_now=True,
    editable=False,
    null = True,
    )

  owner = models.ForeignKey(
    User,
    on_delete=models.PROTECT,
    blank = True,
    null = True,
    )

  title = models.CharField(
    max_length=255,
    )

  description = models.TextField(
    blank=True,
    null=True,
    )

  style = models.CharField(
    max_length=255,
    )

  def __str__(self):
    return self.title

class BookmarkTag(models.Model):
  class Meta:
    ordering = ['-id']

  created_at = models.DateTimeField(
    auto_now_add=True,
    editable=False,
    )

  owner = models.ForeignKey(
    User,
    on_delete=models.PROTECT,
    blank = True,
    null = True,
    )

  bookmark = models.ForeignKey(
    Bookmark,
    on_delete=models.PROTECT,
    )

  tag = models.ForeignKey(
    Tag,
    on_delete=models.PROTECT,
    )
