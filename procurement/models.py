import uuid
from django.db import models
from django.db.models import Sum, F
from core.models import Store, StoreStaff
from inventory.models import Product, Category


class ProcurementPlan(models.Model):
    STATUS_CHOICES = [
        ('draft',       'Draft'),
        ('approved',    'Approved'),
        ('in_progress', 'In Progress'),
        ('fulfilled',   'Fulfilled'),
        ('cancelled',   'Cancelled'),
    ]

    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    store        = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='procurement_plans')
    title        = models.CharField(max_length=300)
    status       = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    planned_date = models.DateField()
    notes        = models.TextField(blank=True)
    created_by   = models.ForeignKey(StoreStaff, on_delete=models.SET_NULL, null=True, blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)
    fulfilled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} ({self.get_status_display()})"

    @property
    def total_items(self):
        return self.items.count()

    @property
    def estimated_cost(self):
        return self.items.aggregate(
            total=Sum(F('planned_qty') * F('estimated_unit_cost'))
        )['total'] or 0


class ProcurementItem(models.Model):
    id                     = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    plan                   = models.ForeignKey(ProcurementPlan, on_delete=models.CASCADE, related_name='items')
    product                = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True, related_name='procurement_items')
    new_product_name       = models.CharField(max_length=300, blank=True)
    category               = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True)

    planned_qty            = models.PositiveIntegerField(default=1)
    estimated_unit_cost    = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    supplier_name          = models.CharField(max_length=300, blank=True)
    supplier_location      = models.CharField(max_length=300, blank=True)
    current_stock          = models.IntegerField(default=0)

    actual_qty             = models.PositiveIntegerField(null=True, blank=True)
    actual_unit_cost       = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    is_paid                = models.BooleanField(default=True)
    available_for_preorder = models.BooleanField(default=False)
    selling_price          = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    is_fulfilled           = models.BooleanField(default=False)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f"{self.planned_qty}x {self.display_name}"

    @property
    def display_name(self):
        return self.product.name if self.product else self.new_product_name
