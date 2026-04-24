import uuid
import secrets
from django.db import models
from django.utils import timezone
from core.models import Store
from inventory.models import Product


class PreOrder(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('ready', 'Ready for Pickup'),
        ('fulfilled', 'Fulfilled'),
        ('cancelled', 'Cancelled'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='preorders')
    customer_name = models.CharField(max_length=200)
    customer_phone = models.CharField(max_length=20)
    customer_whatsapp = models.CharField(max_length=20, blank=True)
    customer_city = models.CharField(max_length=100, blank=True)
    customer_email = models.EmailField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    notes = models.TextField(blank=True, help_text='Customer notes or special requests')
    staff_notes = models.TextField(blank=True, help_text='Internal notes from staff')
    desired_date = models.DateField(null=True, blank=True)
    pickup_code = models.CharField(max_length=16, blank=True, db_index=True)
    pickup_code_generated_at = models.DateTimeField(null=True, blank=True)
    pickup_code_expires_at = models.DateTimeField(null=True, blank=True)
    pickup_code_used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"PreOrder by {self.customer_name} - {self.get_status_display()}"

    @property
    def pickup_code_is_active(self):
        if not self.pickup_code or self.status != 'ready' or self.pickup_code_used_at:
            return False
        if self.pickup_code_expires_at and self.pickup_code_expires_at <= timezone.now():
            return False
        return True

    def activate_pickup_code(self):
        if self.pickup_code_is_active:
            return self.pickup_code

        prefix = ''.join(ch for ch in self.store.slug.upper() if ch.isalnum())[:3] or 'PO'
        alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'

        for _ in range(30):
            candidate = f"{prefix}-{''.join(secrets.choice(alphabet) for _ in range(6))}"
            if not PreOrder.objects.exclude(pk=self.pk).filter(pickup_code=candidate).exists():
                self.pickup_code = candidate
                self.pickup_code_generated_at = timezone.now()
                self.pickup_code_expires_at = None
                self.pickup_code_used_at = None
                return candidate
        raise RuntimeError('Could not generate a unique pickup code.')

    def expire_pickup_code(self, used=False):
        if not self.pickup_code:
            return
        now = timezone.now()
        self.pickup_code_expires_at = now
        if used:
            self.pickup_code_used_at = now


class PreOrderItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    preorder = models.ForeignKey(PreOrder, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True, related_name='preorder_items')
    item_description = models.CharField(max_length=500, help_text='Product name snapshot or custom request')
    quantity = models.PositiveIntegerField(default=1)
    unit_label = models.CharField(max_length=30, default='unit')
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    selected_color = models.CharField(max_length=100, blank=True)
    selected_size = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f"{self.quantity}x {self.item_description}"

    @property
    def line_total(self):
        return self.quantity * self.unit_price

    @property
    def variation_summary(self):
        parts = []
        if self.selected_color:
            parts.append(f"Color: {self.selected_color}")
        if self.selected_size:
            parts.append(f"Size: {self.selected_size}")
        return " | ".join(parts)
