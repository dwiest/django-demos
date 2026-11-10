from django.contrib import admin

from .models import Catalog, Product, ProductVariant


class VariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 1


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'published']
    list_filter = ['published', 'catalogs']
    search_fields = ['name', 'description']
    prepopulated_fields = {'slug': ('name',)}
    filter_horizontal = ['catalogs']
    inlines = [VariantInline]


@admin.register(Catalog)
class CatalogAdmin(admin.ModelAdmin):
    list_display = ['name', 'published']
    prepopulated_fields = {'slug': ('name',)}


from .models import StoreOrder, StoreOrderItem, ShippingAddress, OrderEvent


@admin.register(StoreOrder)
class StoreOrderAdmin(admin.ModelAdmin):
    list_display = ['number', 'email', 'status', 'total', 'created_at', 'fulfilled_at']
    list_filter = ['status', 'payment_method']
    search_fields = ['email', 'tracking_number', 'shipping_address__name']
    readonly_fields = [field.name for field in StoreOrder._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def change_view(self, request, object_id, form_url='', extra_context=None):
        from django.shortcuts import redirect
        # All writes pass through the audited store management workflow.
        return redirect('demos:store:order_edit', pk=object_id)
