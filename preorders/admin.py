from django.contrib import admin
from .models import PreOrder, PreOrderItem


class PreOrderItemInline(admin.TabularInline):
    model = PreOrderItem
    extra = 1


@admin.register(PreOrder)
class PreOrderAdmin(admin.ModelAdmin):
    list_display = ['customer_name', 'store', 'customer_phone', 'status', 'desired_date', 'created_at']
    list_filter = ['store', 'status']
    search_fields = ['customer_name', 'customer_phone']
    inlines = [PreOrderItemInline]
