from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('demos', '0012_bookmark_enrichment')]
    operations = [
        migrations.AddField(model_name='bookmarkaisettings', name='download_on_create', field=models.BooleanField(default=False)),
        migrations.AddField(model_name='bookmarkaisettings', name='enrich_on_create', field=models.BooleanField(default=False)),
        migrations.AddField(model_name='bookmarkaisettings', name='failed_attempt_retention_days', field=models.PositiveIntegerField(default=30, null=True, blank=True)),
    ]
