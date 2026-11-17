from django.contrib import admin
from .application_catalog import BY_KEY
from .application_models import Application


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'enabled', 'required_permission')
    list_editable = ('enabled',)
    list_filter = ('enabled',)
    search_fields = ('key',)
    readonly_fields = ('key', 'title', 'category', 'required_permission')
    fields = ('title', 'key', 'category', 'enabled', 'required_permission')

    def title(self, obj):
        return str(obj)

    def category(self, obj):
        app = BY_KEY.get(obj.key)
        return app.category if app else ''

    def required_permission(self, obj):
        app = BY_KEY.get(obj.key)
        return app.permission if app else ''

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
