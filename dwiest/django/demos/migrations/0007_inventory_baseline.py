# Adopt Inventory tables owned by the legacy demos umbrella app.

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def ensure_inventory_tables(apps, schema_editor):
    """Adopt existing umbrella-app tables without rewriting their data."""
    tables = set(schema_editor.connection.introspection.table_names())
    for name in ('InventoryItem', 'InventoryList', 'InventoryEntry'):
        model = apps.get_model('demos', name)
        if model._meta.db_table not in tables:
            schema_editor.create_model(model)
            tables.add(model._meta.db_table)
        else:
            with schema_editor.connection.cursor() as cursor:
                columns = {c.name for c in schema_editor.connection.introspection.get_table_description(
                    cursor, model._meta.db_table)}
            missing = {f.column for f in model._meta.local_fields} - columns
            if missing:
                raise RuntimeError('Inventory table %s is missing columns: %s' % (
                    model._meta.db_table, ', '.join(sorted(missing))))


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('demos', '0006_bookmark'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(database_operations=[], state_operations=[
            migrations.CreateModel(
                name='InventoryEntry',
                fields=[
                    ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                    ('created_at', models.DateTimeField(auto_now_add=True)),
                    ('last_modified', models.DateTimeField(auto_now=True)),
                    ('status', models.IntegerField(default=0)),
                    ('date_added', models.DateField(auto_now_add=True)),
                    ('quantity', models.IntegerField(default=1)),
                ],
                options={
                    'ordering': ['date_added'],
                },
            ),
            migrations.CreateModel(
                name='InventoryList',
                fields=[
                    ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                    ('created_at', models.DateTimeField(auto_now_add=True)),
                    ('last_modified', models.DateTimeField(auto_now=True)),
                    ('status', models.IntegerField(default=0)),
                    ('name', models.CharField(max_length=255, unique=True)),
                    ('description', models.CharField(max_length=255)),
                    ('owner', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
                ],
                options={
                    'ordering': ['last_modified'],
                },
            ),
            migrations.CreateModel(
                name='InventoryItem',
                fields=[
                    ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                    ('created_at', models.DateTimeField(auto_now_add=True)),
                    ('last_modified', models.DateTimeField(auto_now=True)),
                    ('status', models.IntegerField(default=0)),
                    ('name', models.CharField(max_length=255, unique=True)),
                    ('description', models.CharField(max_length=255)),
                    ('owner', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
                ],
                options={
                    'abstract': False,
                },
            ),
            migrations.AddField(
                model_name='inventoryentry',
                name='inventory_list',
                field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='demos.inventorylist'),
            ),
            migrations.AddField(
                model_name='inventoryentry',
                name='item',
                field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='demos.inventoryitem'),
            ),
            migrations.AddField(
                model_name='inventoryentry',
                name='owner',
                field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL),
            ),
        ]),
        migrations.RunPython(ensure_inventory_tables, migrations.RunPython.noop),
    ]
