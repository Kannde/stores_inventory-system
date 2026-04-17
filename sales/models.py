import uuid
from django.db import models
from django.db.models import Sum, F
from core.models import Store, StoreStaff
from inventory.models import Product, Package


class Sale(models.Model):
    STATUS_CHOICES = [
        ('completed', 'Completed'),
        ('refunded', 'Refunded'),
        ('partial_refund', 'Partial Refund'),
    ]
    PAYMENT_CHOICES = [
        ('cash', 'Cash'),
        ('momo', 'Mobile Money'),
        ('card', 'Card'),
        ('credit', 'Credit'),
        ('mixed', 'Mixed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='sales')
    staff = models.ForeignKey(StoreStaff, on_delete=models.SET_NULL, null=True, blank=True, related_name='sales')
    receipt_number = models.CharField(max_length=30, unique=True, blank=True)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    change_given = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    payment_method = models.CharField(max_length=10, choices=PAYMENT_CHOICES, default='cash')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='completed')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Sale {self.receipt_number} - {self.total_amount}"

    def save(self, *args, **kwargs):
        if not self.receipt_number:
            import uuid as _uuid
            from django.utils import timezone
            today = timezone.now().strftime('%Y%m%d')
            short = _uuid.uuid4().hex[:5].upper()
            self.receipt_number = f"{self.store.slug[:6].upper()}-{today}-{short}"
        super().save(*args, **kwargs)

    def recalculate_total(self):
        self.total_amount = self.items.aggregate(
            total=Sum('line_total')
        )['total'] or 0
        self.save(update_fields=['total_amount'])


class SaleItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True, related_name='sale_items')
    package = models.ForeignKey(Package, on_delete=models.SET_NULL, null=True, blank=True, related_name='sale_items')
    item_name = models.CharField(max_length=300, help_text='Snapshot of product/package name at time of sale')
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    line_total = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f"{self.quantity}x {self.item_name}"

    def save(self, *args, **kwargs):
        self.line_total = self.quantity * self.unit_price
        super().save(*args, **kwargs)
