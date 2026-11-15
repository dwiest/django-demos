from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('demos', '0009_bookmark_ai')]
    operations = [
        migrations.AddField(
            model_name='bookmarkaisettings', name='blocked_domains',
            field=models.JSONField(blank=True, default=list),
        ),
    ]
