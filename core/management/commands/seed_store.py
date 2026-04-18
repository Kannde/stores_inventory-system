"""
Usage:
  python manage.py seed_store --store <slug>
  python manage.py seed_store --store <slug> --sales 500 --days 180
  python manage.py seed_store --store <slug> --clear
"""
import random
from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.db import transaction

from core.models import Store, StoreStaff
from inventory.models import Category, Product, Supplier, SupplierTransaction, StockMovement
from sales.models import Sale, SaleItem, CreditAccount
from preorders.models import PreOrder, PreOrderItem


CATEGORIES = [
    ("Beverages", [
        ("Coca-Cola 500ml", 5.00, 3.20, "bottle"),
        ("Fanta Orange 500ml", 5.00, 3.20, "bottle"),
        ("Sprite 500ml", 5.00, 3.20, "bottle"),
        ("Malta Guinness 330ml", 4.50, 2.80, "bottle"),
        ("Water Sachet (30 pcs)", 7.00, 5.00, "pack"),
        ("Alvaro Pineapple 330ml", 5.50, 3.50, "can"),
        ("Energy Drink 250ml", 8.00, 5.50, "can"),
        ("Fruit Juice 1L", 18.00, 12.00, "carton"),
    ]),
    ("Food & Groceries", [
        ("Titus Sardines 155g", 9.50, 6.50, "tin"),
        ("Geisha Mackerel 200g", 11.00, 7.50, "tin"),
        ("Tomato Paste 70g", 3.50, 2.00, "sachet"),
        ("Maggi Cube (100 pcs)", 14.00, 10.00, "box"),
        ("Sugar 1kg", 12.00, 9.00, "bag"),
        ("Rice 5kg", 65.00, 50.00, "bag"),
        ("Cooking Oil 1L", 28.00, 22.00, "bottle"),
        ("Spaghetti 500g", 9.00, 6.50, "pack"),
        ("Bread Loaf", 14.00, 10.00, "loaf"),
        ("Eggs (30 pcs)", 55.00, 42.00, "crate"),
    ]),
    ("Snacks & Confectionery", [
        ("Pringles 40g", 12.00, 8.00, "tube"),
        ("Digestive Biscuits 200g", 10.00, 7.00, "pack"),
        ("Chocolate Bar 50g", 8.00, 5.00, "bar"),
        ("Plantain Chips 100g", 7.00, 4.50, "pack"),
        ("Popcorn 80g", 5.00, 3.00, "bag"),
        ("Chewing Gum 10-strip", 2.00, 1.00, "pack"),
    ]),
    ("Household & Cleaning", [
        ("Omo Detergent 500g", 18.00, 13.00, "bag"),
        ("Ariel Washing Powder 1kg", 35.00, 26.00, "bag"),
        ("Dettol Soap 100g", 8.50, 5.50, "bar"),
        ("Key Soap 200g", 5.00, 3.00, "bar"),
        ("Bleach 750ml", 12.00, 8.00, "bottle"),
        ("Broom", 25.00, 17.00, "piece"),
        ("Toilet Paper 4-roll", 15.00, 10.00, "pack"),
        ("Sponge & Scrubber", 6.00, 3.50, "piece"),
    ]),
    ("Personal Care", [
        ("Vaseline 250ml", 22.00, 16.00, "jar"),
        ("Lux Soap 100g", 7.00, 4.50, "bar"),
        ("Dove Body Wash 250ml", 38.00, 28.00, "bottle"),
        ("Deodorant Roll-on 50ml", 30.00, 22.00, "bottle"),
        ("Toothpaste 100ml", 16.00, 11.00, "tube"),
        ("Toothbrush", 8.00, 5.00, "piece"),
        ("Sanitary Pads 8-pack", 15.00, 10.00, "pack"),
        ("Baby Powder 200g", 20.00, 14.00, "tin"),
    ]),
    ("Stationery", [
        ("Exercise Book 40pg", 5.00, 3.00, "piece"),
        ("Pen (10-pack)", 12.00, 8.00, "pack"),
        ("Pencil (12-pack)", 10.00, 6.50, "pack"),
        ("A4 Paper (ream)", 55.00, 42.00, "ream"),
        ("Scotch Tape", 6.00, 3.50, "roll"),
        ("Stapler", 35.00, 24.00, "piece"),
    ]),
    ("Phone & Accessories", [
        ("Phone Charger USB-C", 45.00, 30.00, "piece"),
        ("Earphones", 35.00, 22.00, "piece"),
        ("Screen Protector", 15.00, 8.00, "piece"),
        ("Phone Case (generic)", 20.00, 12.00, "piece"),
        ("USB Cable 1m", 20.00, 12.00, "piece"),
        ("Power Bank 5000mAh", 120.00, 85.00, "piece"),
    ]),
    ("Alcohol & Spirits", [
        ("Club Beer 330ml", 9.00, 6.00, "bottle"),
        ("Star Beer 330ml", 9.00, 6.00, "bottle"),
        ("Smirnoff Ice 275ml", 12.00, 8.00, "bottle"),
        ("Alomo Bitters 200ml", 18.00, 12.00, "bottle"),
        ("Akpeteshie 375ml", 22.00, 15.00, "bottle"),
    ]),
]

STAFF_NAMES = ["Ama Mensah", "Kofi Asante", "Abena Owusu", "Kweku Darko", "Akua Boateng"]

CUSTOMER_NAMES = [
    "Emmanuel Tetteh", "Grace Asiedu", "Samuel Nkrumah", "Comfort Quaye", "Francis Appiah",
    "Esther Osei", "Daniel Antwi", "Mary Agyemang", "Joshua Boateng", "Rebecca Mensah",
    "Isaac Adjei", "Patience Ofori", "Benjamin Asare", "Evelyn Darko", "Richard Acheampong",
    "Cecelia Opoku", "Patrick Owusu", "Agnes Nyarko", "Stephen Asante", "Naomi Frimpong",
]

PAYMENT_METHODS = ['cash', 'cash', 'cash', 'momo', 'momo', 'card', 'credit', 'mixed']


class Command(BaseCommand):
    help = 'Seed a store with products, suppliers, and sales history'

    def add_arguments(self, parser):
        parser.add_argument('--store', required=True, help='Store slug')
        parser.add_argument('--sales', type=int, default=300, help='Number of sales to create (default 300)')
        parser.add_argument('--days', type=int, default=90, help='History spread in days (default 90)')
        parser.add_argument('--clear', action='store_true', help='Clear existing seed data before seeding')

    def handle(self, *args, **options):
        slug = options['store']
        try:
            store = Store.objects.get(slug=slug)
        except Store.DoesNotExist:
            raise CommandError(f"Store '{slug}' not found")

        if options['clear']:
            self._clear(store)

        with transaction.atomic():
            self._seed(store, options['sales'], options['days'])

        self.stdout.write(self.style.SUCCESS(
            f"\nDone! Seeded store '{store.name}' with products and {options['sales']} sales."
        ))

    def _clear(self, store):
        self.stdout.write("Clearing existing data...")
        Sale.objects.filter(store=store).delete()
        Product.objects.filter(store=store).delete()
        Category.objects.filter(store=store).delete()
        Supplier.objects.filter(store=store).delete()
        StoreStaff.objects.filter(store=store).delete()
        PreOrder.objects.filter(store=store).delete()
        self.stdout.write("  Cleared.")

    def _seed(self, store, num_sales, num_days):
        # ── Staff ───────────────────────────────────────────────────────────
        self.stdout.write("Creating staff...")
        staff_members = list(StoreStaff.objects.filter(store=store, is_active=True))
        if not staff_members:
            for i, name in enumerate(STAFF_NAMES):
                s = StoreStaff.objects.create(
                    store=store, name=name,
                    role='manager' if i == 0 else 'sales', is_active=True,
                )
                staff_members.append(s)

        # ── Supplier ────────────────────────────────────────────────────────
        self.stdout.write("Creating suppliers...")
        supplier, _ = Supplier.objects.get_or_create(
            store=store, name="Main Distributor",
            defaults={'contact_person': 'John Doe', 'phone': '0244000001', 'ownership': 'external'},
        )

        # ── Categories & Products ───────────────────────────────────────────
        self.stdout.write("Creating categories and products...")
        all_products = []
        for cat_name, items in CATEGORIES:
            cat, _ = Category.objects.get_or_create(store=store, name=cat_name)
            for name, price, cost, unit in items:
                stock = random.randint(20, 200)
                prod, created = Product.objects.get_or_create(
                    store=store, name=name,
                    defaults={
                        'category': cat,
                        'supplier': supplier,
                        'unit_price': Decimal(str(price)),
                        'cost_price': Decimal(str(cost)),
                        'unit_label': unit,
                        'stock_qty': stock,
                        'reorder_level': 10,
                        'available_for_preorder': random.random() < 0.4,
                        'preorder_lead_days': random.choice([3, 5, 7, 14]) if random.random() < 0.5 else None,
                    }
                )
                if created:
                    StockMovement.objects.create(
                        product=prod, movement_type='in',
                        quantity=stock, reason='Initial stock', reference='SEED',
                    )
                all_products.append(prod)

        self.stdout.write(f"  {len(all_products)} products ready.")

        # ── Supplier transaction (initial purchase) ─────────────────────────
        total_cost = sum(p.cost_price * p.stock_qty for p in all_products)
        SupplierTransaction.objects.get_or_create(
            supplier=supplier,
            description='Initial stock purchase',
            defaults={
                'tx_type': 'purchase',
                'amount': total_cost,
                'date': (timezone.now() - timedelta(days=num_days + 5)).date(),
            }
        )

        # ── Sales ────────────────────────────────────────────────────────────
        self.stdout.write(f"Creating {num_sales} sales over {num_days} days...")
        now = timezone.now()
        created_count = 0

        for i in range(num_sales):
            days_ago = random.randint(0, num_days)
            hours_ago = random.randint(0, 23)
            sale_time = now - timedelta(days=days_ago, hours=hours_ago)

            method = random.choice(PAYMENT_METHODS)
            staff = random.choice(staff_members)
            needs_customer = method in ('credit', 'mixed')
            customer = random.choice(CUSTOMER_NAMES) if needs_customer else ''
            customer_phone = f"024{random.randint(1000000, 9999999)}" if needs_customer else ''

            num_items = random.randint(1, 6)
            picked = random.sample(all_products, min(num_items, len(all_products)))

            sale = Sale(
                store=store,
                staff=staff,
                payment_method=method,
                customer_name=customer,
                customer_phone=customer_phone,
                created_at=sale_time,
            )
            sale.save()

            # Manually set created_at (auto_now_add ignores assignment)
            Sale.objects.filter(pk=sale.pk).update(created_at=sale_time)

            total = Decimal('0')
            for prod in picked:
                qty = random.randint(1, 5)
                unit_price = prod.unit_price
                line_total = unit_price * qty
                total += line_total
                SaleItem.objects.create(
                    sale=sale, product=prod, item_name=prod.name,
                    quantity=qty, unit_price=unit_price, line_total=line_total,
                )

            if method == 'cash':
                amount_paid = total + Decimal(str(random.choice([0, 0, 0, 5, 10, 20])))
            elif method == 'credit':
                amount_paid = Decimal('0')
            elif method == 'mixed':
                amount_paid = (total * Decimal('0.5')).quantize(Decimal('0.01'))
            else:
                amount_paid = total

            change = max(Decimal('0'), amount_paid - total)
            Sale.objects.filter(pk=sale.pk).update(
                total_amount=total, amount_paid=amount_paid, change_given=change
            )

            if method in ('credit', 'mixed') and customer:
                CreditAccount.objects.create(
                    sale=sale, store=store,
                    customer_name=customer, customer_phone=customer_phone,
                    total_amount=total, amount_paid=amount_paid,
                    is_settled=(method == 'mixed' and random.random() < 0.3),
                )

            created_count += 1
            if created_count % 50 == 0:
                self.stdout.write(f"  {created_count}/{num_sales} sales created...")

        # ── Preorders ────────────────────────────────────────────────────────
        self.stdout.write("Creating sample preorders...")
        preorder_products = [p for p in all_products if p.available_for_preorder]
        for _ in range(min(20, len(preorder_products) * 2)):
            customer = random.choice(CUSTOMER_NAMES)
            po = PreOrder.objects.create(
                store=store,
                customer_name=customer,
                customer_phone=f"054{random.randint(1000000,9999999)}",
                customer_whatsapp=f"054{random.randint(1000000,9999999)}",
                customer_city=random.choice(["Accra", "Kumasi", "Takoradi", "Tamale", "Cape Coast"]),
                status=random.choice(['pending', 'pending', 'confirmed', 'fulfilled']),
                notes="Seeded preorder",
            )
            for prod in random.sample(preorder_products, min(random.randint(1, 3), len(preorder_products))):
                qty = random.randint(1, 4)
                PreOrderItem.objects.create(
                    preorder=po, product=prod,
                    item_description=prod.name,
                    quantity=qty,
                    unit_price=prod.unit_price,
                )

        self.stdout.write(f"  {created_count} sales, {PreOrder.objects.filter(store=store).count()} preorders created.")
