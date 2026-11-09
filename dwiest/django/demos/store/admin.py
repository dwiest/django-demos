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
