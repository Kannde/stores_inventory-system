import uuid

from django.db import models, transaction
from django.db.models import F, Sum
from django.utils import timezone

from core.models import Store
from inventory.models import Product, ProductVariant, StockMovement, Supplier


class Shipment(models.Model):
    METHOD_AIR = 'AIR'
    METHOD_SEA = 'SEA'
    TRANSPORT_CHOICES = [
        (METHOD_AIR, 'Air Freight'),
        (METHOD_SEA, 'Sea Freight'),
    ]

    STATUS_WAREHOUSE = 'WAREHOUSE'
    STATUS_TRANSIT = 'TRANSIT'
    STATUS_PORT = 'PORT'
    STATUS_CUSTOMS = 'CUSTOMS'
    STATUS_ARRIVED = 'ARRIVED'
    STATUS_DELIVERED = 'DELIVERED'
    STATUS_CHOICES = [
        (STATUS_WAREHOUSE, 'At Origin Warehouse'),
        (STATUS_TRANSIT, 'In Transit'),
        (STATUS_PORT, 'At Ghana Port'),
        (STATUS_CUSTOMS, 'At Customs'),
        (STATUS_ARRIVED, 'Ready for Pickup'),
        (STATUS_DELIVERED, 'Delivered'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='shipments')
    tracking_number = models.CharField(max_length=100)
    shipping_company = models.CharField(max_length=100)
    method = models.CharField(max_length=3, choices=TRANSPORT_CHOICES, default=METHOD_SEA)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default=STATUS_WAREHOUSE)
    origin = models.CharField(max_length=100, default='China')
    destination = models.CharField(max_length=100, default='Ghana')
    departure_date = models.DateField(null=True, blank=True)
    estimated_arrival = models.DateField(null=True, blank=True)
    actual_arrival = models.DateField(null=True, blank=True)
    document = models.FileField(upload_to='shipments/', null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = ['store', 'tracking_number']

    def __str__(self):
        return f'{self.tracking_number} - {self.get_status_display()}'

    def save(self, *args, **kwargs):
        old_status = None
        is_new = self._state.adding
        if self.pk:
            old_status = Shipment.objects.filter(pk=self.pk).values_list('status', flat=True).first()

        super().save(*args, **kwargs)

        if is_new:
            ShipmentStatusHistory.objects.create(
                shipment=self,
                status=self.status,
                note='Shipment created.',
            )
        elif old_status and old_status != self.status:
            ShipmentStatusHistory.objects.create(
                shipment=self,
                status=self.status,
            )

    @property
    def packages_pending_receiving(self):
        return self.packages.filter(is_received=False).count()

    @property
    def packages_with_missing_items(self):
        return self.packages.filter(items__received_quantity__lt=models.F('items__expected_quantity')).distinct().count()

    def update_status_if_complete(self):
        packages = self.packages.all()
        if packages.exists() and not packages.filter(is_received=False).exists():
            updates = {'status': self.STATUS_DELIVERED}
            if not self.actual_arrival:
                updates['actual_arrival'] = timezone.now().date()
            Shipment.objects.filter(pk=self.pk).update(**updates)
            self.refresh_from_db(fields=['status', 'actual_arrival'])
            ShipmentStatusHistory.objects.create(
                shipment=self,
                status=self.status,
                note='All packages received and stocked.',
            )

    @property
    def next_pending_package(self):
        for package in self.packages.all():
            if not package.is_received:
                return package
        return None

    @property
    def total_expense_amount(self):
        return self.expenses.aggregate(total=Sum('amount'))['total'] or 0


class ShipmentPackage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    shipment = models.ForeignKey(Shipment, related_name='packages', on_delete=models.CASCADE)
    supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True, blank=True)
    package_code = models.CharField(max_length=100)
    description = models.CharField(max_length=255, blank=True)
    is_received = models.BooleanField(default=False)
    is_fragile = models.BooleanField(default=False)
    is_stocked = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at', 'package_code']
        unique_together = ['shipment', 'package_code']

    def __str__(self):
        return f'{self.package_code} ({self.description or self.shipment.tracking_number})'

    @property
    def items_complete(self):
        items = list(self.items.all())
        return bool(items) and all(item.is_complete for item in items)

    @property
    def missing_items_count(self):
        return sum(1 for item in self.items.all() if item.missing_quantity > 0)

    @property
    def missing_quantity_total(self):
        return sum(item.missing_quantity for item in self.items.all())

    @property
    def allocated_cost(self):
        package_count = self.shipment.packages.count() or 1
        return self.shipment.total_expense_amount / package_count

    def refresh_received_status(self, save=True):
        is_complete = self.items_complete
        if self.is_received != is_complete:
            self.is_received = is_complete
            if save:
                self.save(update_fields=['is_received'])
        elif save:
            self.save(update_fields=['is_received'])
        return self.is_received

    def push_to_inventory(self):
        if self.is_stocked:
            return

        with transaction.atomic():
            # Group by product — same product can appear multiple times (different variants)
            qty_by_product = {}     # pid -> total received qty
            prices_by_product = {}  # pid -> {'cost': ..., 'unit': ..., 'product': obj}
            variant_qty = {}        # (pid, size, color) -> qty

            for item in self.items.select_related('product'):
                if not item.received_quantity:
                    continue
                pid = str(item.product_id)
                qty_by_product[pid] = qty_by_product.get(pid, 0) + item.received_quantity
                if pid not in prices_by_product:
                    prices_by_product[pid] = {'cost': item.cost_price, 'unit': item.unit_price, 'product': item.product}
                else:
                    if item.cost_price is not None:
                        prices_by_product[pid]['cost'] = item.cost_price
                    if item.unit_price is not None:
                        prices_by_product[pid]['unit'] = item.unit_price
                if item.variant_size or item.variant_color:
                    vkey = (pid, item.variant_size, item.variant_color)
                    variant_qty[vkey] = variant_qty.get(vkey, 0) + item.received_quantity

            for pid, qty in qty_by_product.items():
                info = prices_by_product[pid]
                price_updates = {}
                if info['cost'] is not None:
                    price_updates['cost_price'] = info['cost']
                if info['unit'] is not None:
                    price_updates['unit_price'] = info['unit']
                if price_updates:
                    Product.objects.filter(pk=pid).update(**price_updates)
                Product.objects.filter(pk=pid).update(stock_qty=F('stock_qty') + qty)
                StockMovement.objects.create(
                    product=info['product'],
                    movement_type='in',
                    quantity=qty,
                    reason=f'Shipment package received: {self.package_code}',
                    reference=str(self.shipment_id),
                )

            # Update per-variant stock
            for (pid, vsize, vcolor), vqty in variant_qty.items():
                variant_obj, _ = ProductVariant.objects.get_or_create(
                    product_id=pid, size=vsize, color=vcolor,
                    defaults={'stock_qty': 0},
                )
                ProductVariant.objects.filter(pk=variant_obj.pk).update(stock_qty=F('stock_qty') + vqty)

            self.is_stocked = True
            self.save(update_fields=['is_stocked'])

    def complete_receiving(self):
        self.refresh_from_db()
        self.is_received = True
        self.save(update_fields=['is_received'])
        self.push_to_inventory()
        self.shipment.update_status_if_complete()


class ShipmentPackageItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    package = models.ForeignKey(ShipmentPackage, related_name='items', on_delete=models.CASCADE)
    supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True, blank=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='shipment_package_items')
    expected_quantity = models.PositiveIntegerField()
    received_quantity = models.PositiveIntegerField(default=0)
    is_verified = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    variant_size = models.CharField(max_length=50, blank=True)
    variant_color = models.CharField(max_length=50, blank=True)
    cost_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True,
                                     help_text='Actual cost per unit on receipt')
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True,
                                     help_text='Selling price to set on product')
    shortage_reason = models.CharField(max_length=300, blank=True,
                                       help_text='Reason items were short (damaged, missing, short-shipped)')

    class Meta:
        ordering = ['created_at', 'id']

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.product.name} in {self.package.package_code}'

    def save(self, *args, **kwargs):
        self.is_verified = self.received_quantity >= self.expected_quantity
        super().save(*args, **kwargs)

    @property
    def is_complete(self):
        return self.received_quantity >= self.expected_quantity

    @property
    def missing_quantity(self):
        return max(0, self.expected_quantity - self.received_quantity)


class ShipmentStatusHistory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    shipment = models.ForeignKey(Shipment, related_name='history', on_delete=models.CASCADE)
    status = models.CharField(max_length=20)
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.shipment.tracking_number} -> {self.status}'
