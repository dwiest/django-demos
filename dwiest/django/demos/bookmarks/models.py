from django.db import models


class Bookmark(models.Model):
  url = models.CharField(max_length=255)
  title = models.CharField(max_length=255)
  description = models.TextField(blank=True, null=True)
  created_at = models.DateTimeField(auto_now_add=True)
  last_modified = models.DateTimeField(auto_now_add=True)
  article_date = models.DateTimeField(auto_now_add=False, blank=True, null=True)

  def __init__(self, *args, **kwargs):
    super().__init__(*args,**kwargs)

#class Screenshot(models.Model):
#  bookmark = models.ForeignKey(Bookmark)
#  path = models.TextField()
#  created_at = models.DateTimeField(auto_now_add=True)

#class Label(models.Model):
#  name = models.CharField(max_length=255)
#  description = models.TextField(blank=True, null=True)
#  bookmark = models.ManyToMany(Bookmark)
