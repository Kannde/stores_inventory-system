"""
Seed script — run with: python manage.py shell < seed_demo.py
Creates a demo store with products, packages, staff, sales, and preorders.
"""
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from decimal import Decimal
from django.utils import timezone
from datetime import timedelta
import random

from core.models import Store, StoreStaff
from inventory.models import Category, Product, Package, PackageItem, StockMovement
from sales.models import Sale, SaleItem
from preorders.models import PreOrder, PreOrderItem

# ── STORE ──
store, _ = Store.objects.get_or_create(
    slug='kwame-mart',
    defaults={
        'name': 'Kwame Mart',
        'phone': '+233 24 000 1234',
        'location': 'Adum, Kumasi',
        'description': 'General goods & provisions',
        'currency_symbol': 'GH₵',
    }
)

store2, _ = Store.objects.get_or_create(
    slug='ama-electronics',
    defaults={
        'name': 'Ama Electronics',
        'phone': '+233 20 555 9876',
        'location': 'Kejetia, Kumasi',
        'description': 'Phones, accessories & electronics',
        'currency_symbol': 'GH₵',
    }
)

# ── STAFF ──
staff_data = [
    ('Kwame Asante', 'manager', '1234'),
    ('Akua Mensah', 'sales', '5678'),
    ('Yaw Boateng', 'sales', '9012'),
    ('Esi Owusu', 'stock', '3456'),
]
staff_objs = []
for name, role, pin in staff_data:
    s, _ = StoreStaff.objects.get_or_create(
        store=store, name=name,
        defaults={'role': role, 'pin': pin, 'phone': f'+233 {random.randint(20,27)}0 {random.randint(100,999)} {random.randint(1000,9999)}'}
    )
    staff_objs.append(s)

# ── CATEGORIES ──
cat_names = ['Beverages', 'Provisions', 'Personal Care', 'Cleaning', 'Snacks']
cats = {}
for name in cat_names:
    c, _ = Category.objects.get_or_create(store=store, name=name)
    cats[name] = c

# ── PRODUCTS ──
products_data = [
    ('Coca-Cola 500ml', 'Beverages', 8.00, 6.50, 120, 'bottle'),
    ('Fanta Orange 500ml', 'Beverages', 8.00, 6.50, 95, 'bottle'),
    ('Malta Guinness', 'Beverages', 10.00, 8.00, 60, 'bottle'),
    ('Pure Water Sachet', 'Beverages', 0.50, 0.30, 500, 'sachet'),
    ('Voltic 1.5L', 'Beverages', 6.00, 4.50, 80, 'bottle'),
    ('Indomie Instant Noodles', 'Provisions', 5.00, 3.80, 200, 'pack'),
    ('Golden Tree Chocolate', 'Snacks', 12.00, 9.00, 45, 'bar'),
    ('Ideal Milk Tin', 'Provisions', 14.00, 11.00, 75, 'tin'),
    ('Milo 400g', 'Provisions', 45.00, 38.00, 30, 'tin'),
    ('Nescafe Sachet', 'Beverages', 3.00, 2.00, 150, 'sachet'),
    ('Key Soap', 'Cleaning', 6.00, 4.50, 100, 'bar'),
    ('Omo Detergent 500g', 'Cleaning', 18.00, 14.00, 55, 'pack'),
    ('Pepsodent Toothpaste', 'Personal Care', 12.00, 9.00, 40, 'tube'),
    ('Dettol Soap', 'Personal Care', 15.00, 11.00, 35, 'bar'),
    ('Sugar 1kg', 'Provisions', 16.00, 13.00, 50, 'bag'),
    ('Rice 5kg (Local)', 'Provisions', 85.00, 70.00, 25, 'bag'),
    ('Cooking Oil 1L', 'Provisions', 32.00, 26.00, 40, 'bottle'),
    ('Sardine Tin', 'Provisions', 8.00, 6.00, 90, 'tin'),
    ('Biscuit Cabin', 'Snacks', 3.00, 2.00, 180, 'pack'),
    ('Fan Yoghurt', 'Beverages', 7.00, 5.00, 45, 'cup'),
]

prod_objs = []
for name, cat, price, cost, stock, unit in products_data:
    p, _ = Product.objects.get_or_create(
        store=store, name=name,
        defaults={
            'category': cats[cat],
            'unit_price': Decimal(str(price)),
            'cost_price': Decimal(str(cost)),
            'stock_qty': stock,
            'unit_label': unit,
            'reorder_level': 10 if stock > 50 else 5,
        }
    )
    prod_objs.append(p)

# ── PACKAGES ──
pkg1, created = Package.objects.get_or_create(
    store=store, name='Student Starter Pack',
    defaults={'description': 'Essential provisions for school', 'package_price': Decimal('120.00')}
)
if created:
    PackageItem.objects.create(package=pkg1, product=prod_objs[5], quantity=5)   # 5x Indomie
    PackageItem.objects.create(package=pkg1, product=prod_objs[8], quantity=1)   # 1x Milo
    PackageItem.objects.create(package=pkg1, product=prod_objs[7], quantity=2)   # 2x Ideal Milk
    PackageItem.objects.create(package=pkg1, product=prod_objs[14], quantity=1)  # 1x Sugar

pkg2, created = Package.objects.get_or_create(
    store=store, name='Party Drinks Combo',
    defaults={'description': '12 mixed drinks for events', 'package_price': Decimal('90.00')}
)
if created:
    PackageItem.objects.create(package=pkg2, product=prod_objs[0], quantity=4)   # 4x Coke
    PackageItem.objects.create(package=pkg2, product=prod_objs[1], quantity=4)   # 4x Fanta
    PackageItem.objects.create(package=pkg2, product=prod_objs[2], quantity=4)   # 4x Malta

pkg3, created = Package.objects.get_or_create(
    store=store, name='Household Essentials',
    defaults={'description': 'Cleaning & personal care basics', 'package_price': Decimal('55.00')}
)
if created:
    PackageItem.objects.create(package=pkg3, product=prod_objs[10], quantity=2)  # 2x Key Soap
    PackageItem.objects.create(package=pkg3, product=prod_objs[11], quantity=1)  # 1x Omo
    PackageItem.objects.create(package=pkg3, product=prod_objs[12], quantity=1)  # 1x Pepsodent
    PackageItem.objects.create(package=pkg3, product=prod_objs[13], quantity=1)  # 1x Dettol

# ── DEMO SALES (last 14 days) ──
now = timezone.now()
if Sale.objects.filter(store=store).count() < 5:
    for day_offset in range(14, -1, -1):
        num_sales = random.randint(2, 8)
        for _ in range(num_sales):
            sale_time = now - timedelta(days=day_offset, hours=random.randint(7, 20), minutes=random.randint(0, 59))
            staff = random.choice(staff_objs[:3])
            pay = random.choice(['cash', 'cash', 'cash', 'momo', 'momo', 'card'])

            sale = Sale.objects.create(
                store=store, staff=staff, payment_method=pay,
                created_at=sale_time,
            )
            # Override auto_now_add
            Sale.objects.filter(pk=sale.pk).update(created_at=sale_time)

            total = Decimal('0')
            num_items = random.randint(1, 5)
            used = set()
            for _ in range(num_items):
                prod = random.choice(prod_objs)
                if prod.pk in used:
                    continue
                used.add(prod.pk)
                qty = random.randint(1, 4)
                line = prod.unit_price * qty
                total += line
                SaleItem.objects.create(
                    sale=sale, product=prod,
                    item_name=prod.name, quantity=qty,
                    unit_price=prod.unit_price, line_total=line,
                )

            sale.total_amount = total
            sale.amount_paid = total
            sale.save(update_fields=['total_amount', 'amount_paid'])

# ── DEMO PREORDERS ──
if PreOrder.objects.filter(store=store).count() < 2:
    po1 = PreOrder.objects.create(
        store=store, customer_name='Kofi Agyeman',
        customer_phone='+233 24 888 1234',
        notes='Please deliver to KNUST campus gate',
        desired_date=now.date() + timedelta(days=2),
    )
    PreOrderItem.objects.create(preorder=po1, item_description='Rice 25kg bag', quantity=2, unit_label='bag')
    PreOrderItem.objects.create(preorder=po1, item_description='Cooking Oil 5L', quantity=3, unit_label='gallon')

    po2 = PreOrder.objects.create(
        store=store, customer_name='Abena Serwaa',
        customer_phone='+233 20 777 5678',
        status='confirmed',
        notes='For wedding reception, need by Saturday',
        desired_date=now.date() + timedelta(days=5),
    )
    PreOrderItem.objects.create(preorder=po2, item_description='Coca-Cola 1.5L', quantity=24, unit_label='bottle')
    PreOrderItem.objects.create(preorder=po2, item_description='Fanta 1.5L', quantity=12, unit_label='bottle')
    PreOrderItem.objects.create(preorder=po2, item_description='Malta Guinness', quantity=24, unit_label='bottle')

print('✓ Demo data seeded successfully!')
print(f'  Store: {store.name} (/{store.slug}/)')
print(f'  Store 2: {store2.name} (/{store2.slug}/)')
print(f'  Products: {Product.objects.filter(store=store).count()}')
print(f'  Packages: {Package.objects.filter(store=store).count()}')
print(f'  Staff: {StoreStaff.objects.filter(store=store).count()}')
print(f'  Sales: {Sale.objects.filter(store=store).count()}')
print(f'  PreOrders: {PreOrder.objects.filter(store=store).count()}')
