import uuid
import random
from django.db import models
from django.db.models import Sum, F
from core.models import Store


class Category(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='categories')
    name = models.CharField(max_length=100)
    sort_order = models.IntegerField(default=0)
    expiry_warning_days = models.PositiveIntegerField(default=30, help_text='Days before expiry to show warning')
    sku_prefix = models.CharField(max_length=5, blank=True, help_text='2-4 letter prefix for SKUs, e.g. BEV, CLN')

    class Meta:
        ordering = ['sort_order', 'name']
        verbose_name_plural = 'Categories'
        unique_together = ['store', 'name']

    def __str__(self):
        return self.name


class Supplier(models.Model):
    OWNERSHIP_CHOICES = [
        ('external', 'External Supplier'),
        ('store_owned', 'Store-Owned Supplier'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='suppliers')
    name = models.CharField(max_length=200)
    contact_person = models.CharField(max_length=200, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    ownership = models.CharField(max_length=15, choices=OWNERSHIP_CHOICES, default='external')
    outstanding_balance = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    @property
    def is_creditor(self):
        return self.ownership == 'external' and self.outstanding_balance > 0

    @property
    def total_purchased(self):
        return self.transactions.filter(
            tx_type__in=['purchase', 'investment']
        ).aggregate(t=Sum('amount'))['t'] or 0

    @property
    def total_paid(self):
        return self.transactions.filter(
            tx_type__in=['payment', 'return', 'dividend']
        ).aggregate(t=Sum('amount'))['t'] or 0


class SupplierTransaction(models.Model):
    TX_CHOICES = [
        ('purchase', 'Purchase'),
        ('payment', 'Payment'),
        ('return', 'Return'),
        ('investment', 'Investment'),
        ('dividend', 'Dividend'),
    ]
    # balance effect per type: purchase/investment → +amount; payment/return/dividend → -amount

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name='transactions')
    tx_type = models.CharField(max_length=15, choices=TX_CHOICES)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    description = models.CharField(max_length=300, blank=True)
    date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.get_tx_type_display()} {self.amount} — {self.supplier.name}"

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        super().save(*args, **kwargs)
        if is_new:
            if self.tx_type in ('purchase', 'investment'):
                Supplier.objects.filter(pk=self.supplier_id).update(
                    outstanding_balance=F('outstanding_balance') + self.amount
                )
            else:
                Supplier.objects.filter(pk=self.supplier_id).update(
                    outstanding_balance=F('outstanding_balance') - self.amount
                )


class Product(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='products')
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='products')
    supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True, blank=True, related_name='products')
    name = models.CharField(max_length=300)
    sku = models.CharField(max_length=50, blank=True)
    description = models.TextField(blank=True)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    cost_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    unit_label = models.CharField(max_length=30, default='unit', help_text='e.g. piece, kg, bag, bottle')
    stock_qty = models.IntegerField(default=0)
    reorder_level = models.IntegerField(default=5)
    expiry_date = models.DateField(null=True, blank=True)
    barcode = models.CharField(max_length=50, blank=True)
    is_paid = models.BooleanField(default=True, help_text='False if stock was taken on credit from supplier')
    available_for_preorder = models.BooleanField(default=False)
    preorder_lead_days = models.PositiveIntegerField(null=True, blank=True, help_text='Expected days to fulfil a preorder for this product')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.barcode:
            self.barcode = self._generate_barcode()
        super().save(*args, **kwargs)

    def _generate_barcode(self):
        while True:
            code = str(random.randint(100000000000, 999999999999))
            if not Product.objects.filter(store=self.store, barcode=code).exists():
                return code

    @property
    def is_low_stock(self):
        return self.stock_qty <= self.reorder_level

    @property
    def is_out_of_stock(self):
        return self.stock_qty <= 0

    @property
    def days_until_expiry(self):
        if not self.expiry_date:
            return None
        from django.utils import timezone
        return (self.expiry_date - timezone.now().date()).days


class ProductImage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='product_images/')
    sort_order = models.IntegerField(default=0)

    class Meta:
        ordering = ['sort_order']


class Package(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='packages')
    name = models.CharField(max_length=300)
    description = models.TextField(blank=True)
    package_price = models.DecimalField(max_digits=12, decimal_places=2)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    @property
    def items_total(self):
        """Sum of individual product prices * qty in this package."""
        return self.items.aggregate(
            total=Sum(F('quantity') * F('product__unit_price'))
        )['total'] or 0

    @property
    def savings(self):
        return self.items_total - self.package_price


class PackageItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    package = models.ForeignKey(Package, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='package_items')
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        unique_together = ['package', 'product']

    def __str__(self):
        return f"{self.quantity}x {self.product.name}"


class StockMovement(models.Model):
    TYPE_CHOICES = [
        ('in', 'Stock In'),
        ('out', 'Stock Out'),
        ('adjust', 'Adjustment'),
        ('sale', 'Sale'),
        ('return', 'Return'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='movements')
    movement_type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    quantity = models.IntegerField(help_text='Positive for in, negative for out')
    reason = models.CharField(max_length=300, blank=True)
    reference = models.CharField(max_length=100, blank=True, help_text='Sale ID or PO number')
    created_by = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_movement_type_display()}: {self.quantity} {self.product.name}"
