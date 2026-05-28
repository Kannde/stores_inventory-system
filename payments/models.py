import uuid
from django.db import models
from core.models import Store
from sales.models import Sale


class SkrodaTransaction(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('negotiation', 'Negotiation'),
        ('agreed', 'Agreed'),
        ('funded', 'Funded'),
        ('shipped', 'Shipped'),
        ('agent_received', 'Agent Received'),
        ('delivered', 'Delivered'),
        ('completed', 'Completed'),
        ('disputed', 'Disputed'),
        ('cancelled', 'Cancelled'),
        ('refunded', 'Refunded'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sale = models.OneToOneField(Sale, on_delete=models.CASCADE, related_name='skroda_transaction')
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='skroda_transactions')
    skroda_id = models.CharField(max_length=100, unique=True)
    reference_code = models.CharField(max_length=50, blank=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='draft')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    checkout_url = models.TextField(blank=True)
    invite_link = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.reference_code} — {self.get_status_display()}"


class SkrodaWebhookEvent(models.Model):
    event_id = models.CharField(max_length=100, unique=True)
    event_type = models.CharField(max_length=60)
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='skroda_webhook_events')
    payload = models.JSONField()
    processed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.event_id} ({self.event_type})"
