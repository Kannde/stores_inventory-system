import uuid

from django.conf import settings
from django.db import models
from django.utils.text import slugify


class Store(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    owner = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='owned_store',
        blank=True,
        null=True,
    )
    phone = models.CharField(max_length=20, blank=True)
    location = models.CharField(max_length=300, blank=True)
    description = models.TextField(blank=True)
    logo = models.ImageField(upload_to='store_logos/', blank=True, null=True)
    currency_symbol = models.CharField(max_length=10, default='GHS')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            slug = base_slug
            n = 1
            while Store.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{n}"
                n += 1
            self.slug = slug
        super().save(*args, **kwargs)


class StoreSettings(models.Model):
    PAYMENT_POLICY_CHOICES = [
        ('upfront', 'Full Payment Upfront'),
        ('deposit', 'Deposit Required'),
        ('on_delivery', 'Pay on Delivery/Pickup'),
    ]

    store = models.OneToOneField(Store, on_delete=models.CASCADE, related_name='settings')
    allow_partial_payment = models.BooleanField(default=False)
    allow_credit = models.BooleanField(default=False)
    min_deposit_percent = models.DecimalField(max_digits=5, decimal_places=2, default=30)
    preorder_enabled = models.BooleanField(default=True)
    preorder_payment_policy = models.CharField(max_length=20, choices=PAYMENT_POLICY_CHOICES, default='on_delivery')
    preorder_deposit_percent = models.DecimalField(max_digits=5, decimal_places=2, default=30)
    preorder_expected_days = models.PositiveIntegerField(default=7)
    preorder_welcome_message = models.TextField(blank=True)
    preorder_whatsapp_number = models.CharField(max_length=20, blank=True, help_text='WhatsApp number with country code, e.g. 233244000000')
    preorder_all_products = models.BooleanField(default=True, help_text='Show all active products in preorder catalog')
    manager_can_manage_shipments = models.BooleanField(default=False, help_text='Allow store managers to access shipment management')

    # Skroda escrow payment integration
    skroda_enabled = models.BooleanField(default=False, help_text='Enable Skroda escrow payments at checkout')
    skroda_secret_key = models.CharField(max_length=200, blank=True, help_text='Skroda secret API key (sk_live_... or sk_test_...)')
    skroda_webhook_secret = models.CharField(max_length=200, blank=True, help_text='Skroda webhook signing secret')
    skroda_seller_phone = models.CharField(max_length=30, blank=True, help_text='Phone number the store owner registered on Skroda (e.g. 0241234567)')
    skroda_fee_paid_by = models.CharField(
        max_length=10,
        choices=[('buyer', 'Buyer pays fee'), ('seller', 'Seller pays fee')],
        default='buyer',
    )
    skroda_delivery_mode = models.CharField(
        max_length=20,
        choices=[
            ('agent_preferred', 'Agent preferred (use agent if available, fall back to direct)'),
            ('agent_required', 'Agent required (hold transaction if no agent in buyer\'s city)'),
            ('direct_only', 'Direct only (seller ships directly, no agent)'),
        ],
        default='agent_preferred',
    )

    def __str__(self):
        return f"Settings for {self.store.name}"


class StoreStaff(models.Model):
    ROLE_CHOICES = [
        ('manager', 'Manager'),
        ('sales', 'Sales Person'),
        ('stock', 'Stock Keeper'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='staff')
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='store_staff_profile',
        blank=True,
        null=True,
    )
    name = models.CharField(max_length=200)
    phone = models.CharField(max_length=20, blank=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='sales')
    pin = models.CharField(max_length=6, blank=True, help_text='Simple PIN for quick login')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'Store staff'
        constraints = [
            models.UniqueConstraint(
                fields=['store', 'pin'],
                condition=models.Q(pin__gt=''),
                name='unique_store_pin_when_set',
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.get_role_display()}) - {self.store.name}"
