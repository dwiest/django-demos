import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('demos', '0008_inventorytransaction'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(name='BookmarkAISettings', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('encrypted_api_key', models.TextField(blank=True, default='')),
            ('instructions', models.TextField(blank=True, default='')),
            ('model', models.CharField(blank=True, default='', max_length=100)),
            ('owner', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
        ]),
        migrations.CreateModel(name='BookmarkAIAnalysis', fields=[
            ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
            ('bookmark_id', models.PositiveIntegerField(blank=True, null=True)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('expires_at', models.DateTimeField()),
            ('original', models.JSONField(default=dict)), ('proposal', models.JSONField(default=dict)),
            ('sources', models.JSONField(default=list)),
            ('status', models.CharField(default='pending', max_length=16)),
            ('approved', models.JSONField(default=dict)), ('results', models.JSONField(default=list)),
            ('owner', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
        ]),
    ]
