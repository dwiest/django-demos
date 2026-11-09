from django.apps import AppConfig


class StoreConfig(AppConfig):
    name = 'dwiest.django.demos.store'
    label = 'demo_store'
    verbose_name = 'Demo store'
    default_auto_field = 'django.db.models.BigAutoField'

    def ready(self):
        from . import signals  # noqa: F401
