from django.contrib import admin
from .models import Category, Product, ProductImage, Package, PackageItem, StockMovement


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 0


class PackageItemInline(admin.TabularInline):
    model = PackageItem
    extra = 1


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'store', 'sort_order']
    list_filter = ['store']


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'store', 'category', 'unit_price', 'stock_qty', 'reorder_level', 'is_active']
    list_filter = ['store', 'category', 'is_active']
    search_fields = ['name', 'sku']
    inlines = [ProductImageInline]


@admin.register(Package)
class PackageAdmin(admin.ModelAdmin):
    list_display = ['name', 'store', 'package_price', 'is_active']
    list_filter = ['store', 'is_active']
    inlines = [PackageItemInline]


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ['product', 'movement_type', 'quantity', 'reason', 'created_at']
    list_filter = ['movement_type', 'product__store']
    search_fields = ['product__name', 'reason']
