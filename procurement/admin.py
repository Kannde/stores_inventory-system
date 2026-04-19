from django.contrib import admin
from .models import ProcurementPlan, ProcurementItem


class ProcurementItemInline(admin.TabularInline):
    model = ProcurementItem
    extra = 0


@admin.register(ProcurementPlan)
class ProcurementPlanAdmin(admin.ModelAdmin):
    list_display = ['title', 'store', 'status', 'planned_date', 'created_at']
    list_filter = ['store', 'status']
    inlines = [ProcurementItemInline]
