from django.db import models
from .application_catalog import APPLICATIONS, BY_KEY


class Application(models.Model):
    key = models.CharField(primary_key=True, max_length=64)
    enabled = models.BooleanField(default=True)

    class Meta:
        app_label = 'demos'
        ordering = ('key',)
        permissions = tuple((app.codename, 'Can access ' + app.title) for app in APPLICATIONS)

    def __str__(self):
        return BY_KEY[self.key].title if self.key in BY_KEY else self.key
