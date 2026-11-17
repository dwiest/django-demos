"""Join PR 4 preferences to the recovered production migration history."""
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('demos', '0045_merge_20261116_2248'),
        ('demos', '0013_bookmark_creation_preferences'),
    ]
    operations = []
