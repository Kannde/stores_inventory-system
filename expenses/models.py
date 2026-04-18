import uuid
from django.db import models
from core.models import Store, StoreStaff
from inventory.models import Product


class Expense(models.Model):
    CATEGORY_CHOICES = [
        ('salary',    'Staff Salary'),
        ('transport', 'Transportation'),
        ('marketing', 'Marketing'),
        ('breakage',  'Breakages'),
        ('expiry',    'Expired Products'),
        ('utilities', 'Utilities'),
        ('rent',      'Rent'),
        ('other',     'Other'),
    ]

    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    store       = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='expenses')
    category    = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    amount      = models.DecimalField(max_digits=14, decimal_places=2)
    description = models.CharField(max_length=400, blank=True)
    date        = models.DateField()
    recorded_by = models.ForeignKey(StoreStaff, on_delete=models.SET_NULL, null=True, blank=True, related_name='expenses_recorded')
    # For breakage / expiry: link the product so cost auto-fills
    product     = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True, related_name='expense_entries')
    product_qty = models.PositiveIntegerField(default=1)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.get_category_display()} — {self.amount} ({self.date})"
