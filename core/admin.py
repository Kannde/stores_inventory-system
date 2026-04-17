from django.contrib import admin
from .models import Store, StoreStaff


class StoreStaffInline(admin.TabularInline):
    model = StoreStaff
    extra = 0


@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = ['name', 'owner', 'location', 'phone', 'is_active', 'created_at']
    list_filter = ['is_active']
    search_fields = ['name', 'location', 'owner__username', 'owner__first_name']
    inlines = [StoreStaffInline]
    prepopulated_fields = {'slug': ('name',)}
    raw_id_fields = ['owner']


@admin.register(StoreStaff)
class StoreStaffAdmin(admin.ModelAdmin):
    list_display = ['name', 'store', 'role', 'user', 'phone', 'is_active']
    list_filter = ['store', 'role', 'is_active']
    search_fields = ['name', 'phone', 'user__username']
    raw_id_fields = ['user']
