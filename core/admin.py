from django.contrib import admin
from .models import Store, StoreStaff


class StoreStaffInline(admin.TabularInline):
    model = StoreStaff
    extra = 0


@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = ['name', 'location', 'phone', 'is_active', 'created_at']
    list_filter = ['is_active']
    search_fields = ['name', 'location']
    inlines = [StoreStaffInline]
    prepopulated_fields = {'slug': ('name',)}


@admin.register(StoreStaff)
class StoreStaffAdmin(admin.ModelAdmin):
    list_display = ['name', 'store', 'role', 'phone', 'is_active']
    list_filter = ['store', 'role', 'is_active']
    search_fields = ['name', 'phone']
