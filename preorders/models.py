import uuid
from django.db import models
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
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"PreOrder by {self.customer_name} - {self.get_status_display()}"


class PreOrderItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    preorder = models.ForeignKey(PreOrder, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True, related_name='preorder_items')
    item_description = models.CharField(max_length=500, help_text='Product name snapshot or custom request')
    quantity = models.PositiveIntegerField(default=1)
    unit_label = models.CharField(max_length=30, default='unit')
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f"{self.quantity}x {self.item_description}"

    @property
    def line_total(self):
        return self.quantity * self.unit_price
