from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('inventory', '0001_initial'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(
            name='InventoryTransaction',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('operation', models.CharField(max_length=10)),
                ('quantity', models.PositiveIntegerField()),
                ('before', models.IntegerField()),
                ('after', models.IntegerField()),
                ('source', models.CharField(default='manual', max_length=32)),
                ('reference_id', models.CharField(blank=True, max_length=128)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('idempotency_key', models.CharField(blank=True, max_length=128, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('actor', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
                ('entry', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='transactions', to='inventory.inventoryentry')),
            ],
            options={
                'ordering': ['-id'],
            },
        ),
        migrations.AddConstraint(
            model_name='inventorytransaction',
            constraint=models.UniqueConstraint(fields=('actor', 'idempotency_key'), name='inventory_actor_request_unique'),
        ),
    ]
