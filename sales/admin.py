from django.contrib import admin
from .models import Sale, SaleItem


class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 0


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ['receipt_number', 'store', 'staff', 'total_amount', 'payment_method', 'status', 'created_at']
    list_filter = ['store', 'payment_method', 'status']
    search_fields = ['receipt_number']
    inlines = [SaleItemInline]
