from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('demos', '0010_bookmark_ai_blocked_domains'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(name='BookmarkAIAttempt', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('url', models.CharField(max_length=255)),
            ('last_attempted_at', models.DateTimeField(auto_now=True)),
            ('owner', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
        ], options={'unique_together': {('owner', 'url')}}),
    ]
