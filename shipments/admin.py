from django.contrib import admin

from .models import Shipment, ShipmentPackage, ShipmentPackageItem, ShipmentStatusHistory


class ShipmentPackageItemInline(admin.TabularInline):
    model = ShipmentPackageItem
    extra = 0


class ShipmentPackageInline(admin.TabularInline):
    model = ShipmentPackage
    extra = 0


@admin.register(Shipment)
class ShipmentAdmin(admin.ModelAdmin):
    list_display = ('tracking_number', 'shipping_company', 'status', 'method', 'estimated_arrival')
    list_editable = ('status',)
    search_fields = ('tracking_number', 'shipping_company')
    list_filter = ('status', 'method', 'store')
    inlines = [ShipmentPackageInline]


@admin.register(ShipmentPackage)
class ShipmentPackageAdmin(admin.ModelAdmin):
    list_display = ('package_code', 'shipment', 'supplier', 'is_received', 'is_stocked')
    list_filter = ('is_received', 'is_stocked', 'shipment__status')
    search_fields = ('package_code', 'description')
    inlines = [ShipmentPackageItemInline]


@admin.register(ShipmentPackageItem)
class ShipmentPackageItemAdmin(admin.ModelAdmin):
    list_display = ('package', 'product', 'expected_quantity', 'received_quantity', 'is_verified')
    list_filter = ('is_verified', 'package__shipment__store')
    search_fields = ('package__package_code', 'product__name')


@admin.register(ShipmentStatusHistory)
class ShipmentStatusHistoryAdmin(admin.ModelAdmin):
    list_display = ('shipment', 'status', 'created_at')
    list_filter = ('status', 'shipment__store')
    search_fields = ('shipment__tracking_number', 'note')

