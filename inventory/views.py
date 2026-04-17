import json
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.utils.timezone import now
from django.db.models import F, Q, Sum
from core.views import get_store
from .models import Category, Product, ProductImage, Package, PackageItem, StockMovement, Supplier, SupplierTransaction


@login_required
def product_list(request, store_slug):
    store = get_store(store_slug, request.user)
    q = request.GET.get('q', '')
    cat = request.GET.get('cat', '')
    products = Product.objects.filter(store=store)
    if q:
        products = products.filter(Q(name__icontains=q) | Q(sku__icontains=q))
    if cat:
        products = products.filter(category_id=cat)
    categories = Category.objects.filter(store=store)
    return render(request, 'inventory/product_list.html', {
        'store': store, 'products': products, 'categories': categories,
        'q': q, 'cat': cat,
    })


@login_required
def product_form(request, store_slug, pk=None):
    store = get_store(store_slug, request.user)
    product = get_object_or_404(Product, pk=pk, store=store) if pk else None
    store_categories = Category.objects.filter(store=store)
    suppliers = Supplier.objects.filter(store=store, is_active=True)

    # Backfill barcode for existing products that have none
    if product and not product.barcode:
        product.barcode = product._generate_barcode()
        product.save(update_fields=['barcode'])

    if request.method == 'POST':
        data = request.POST
        if product is None:
            product = Product(store=store)
        product.name = data['name']
        product.sku = data.get('sku', '')
        product.description = data.get('description', '')
        product.unit_price = data['unit_price']
        product.cost_price = data.get('cost_price', 0) or 0
        product.unit_label = data.get('unit_label', 'unit')
        product.stock_qty = data.get('stock_qty', 0) or 0
        product.reorder_level = data.get('reorder_level', 5) or 5
        expiry = data.get('expiry_date', '').strip()
        product.expiry_date = expiry if expiry else None

        # Category: may be existing ID or a new standard category name
        cat_val = data.get('category', '').strip()
        if cat_val:
            try:
                import uuid as _uuid
                _uuid.UUID(cat_val)
                product.category_id = cat_val
            except ValueError:
                # It's a name from standard categories — create it
                cat_obj, _ = Category.objects.get_or_create(store=store, name=cat_val)
                product.category = cat_obj
        else:
            product.category = None

        sup_id = data.get('supplier')
        product.supplier_id = sup_id if sup_id else None
        product.available_for_preorder = data.get('available_for_preorder') == 'on'
        product.save()

        for f in request.FILES.getlist('images'):
            ProductImage.objects.create(product=product, image=f)

        return redirect('inventory:product_list', store_slug=store.slug)

    # Build category options: existing store categories + standard ones not yet created
    existing_names = set(store_categories.values_list('name', flat=True))
    standard_not_added = [c for c in STANDARD_RETAIL_CATEGORIES if c not in existing_names]

    return render(request, 'inventory/product_form.html', {
        'store': store, 'product': product,
        'store_categories': store_categories,
        'standard_categories': standard_not_added,
        'suppliers': suppliers,
    })


@login_required
def stock_adjust(request, store_slug, pk):
    store = get_store(store_slug, request.user)
    product = get_object_or_404(Product, pk=pk, store=store)

    if request.method == 'POST':
        movement_type = request.POST['movement_type']
        qty = int(request.POST['quantity'])
        reason = request.POST.get('reason', '')

        if movement_type == 'out':
            qty = -abs(qty)
        elif movement_type == 'in':
            qty = abs(qty)

        StockMovement.objects.create(
            product=product,
            movement_type=movement_type,
            quantity=qty,
            reason=reason,
        )
        product.stock_qty = max(0, product.stock_qty + qty)
        product.save(update_fields=['stock_qty'])
        return redirect('inventory:product_list', store_slug=store.slug)

    movements = StockMovement.objects.filter(product=product)[:20]
    return render(request, 'inventory/stock_adjust.html', {
        'store': store, 'product': product, 'movements': movements,
    })


STANDARD_RETAIL_CATEGORIES = [
    'Beverages', 'Bread & Bakery', 'Breakfast & Cereal', 'Canned & Packaged Goods',
    'Condiments & Sauces', 'Confectionery & Sweets', 'Dairy & Eggs', 'Frozen Foods',
    'Fresh Produce', 'Grains & Rice', 'Meat & Poultry', 'Seafood', 'Snacks & Chips',
    'Spices & Seasonings', 'Beverages - Alcohol', 'Baby & Infant', 'Beauty & Personal Care',
    'Cleaning Supplies', 'Health & Wellness', 'Household Items', 'Laundry & Detergents',
    'Office & Stationery', 'Pet Supplies', 'Toys & Games', 'Clothing & Apparel',
    'Electronics & Accessories', 'Hardware & Tools', 'Automotive', 'Sports & Outdoor',
    'Books & Media', 'Phones & Accessories', 'Fertilizers & Agrochemicals',
    'Veterinary & Animal Feed', 'Fabric & Sewing', 'Gift & Seasonal',
]


@login_required
def category_list(request, store_slug):
    store = get_store(store_slug, request.user)
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        expiry_warning_days = int(request.POST.get('expiry_warning_days', 30) or 30)
        if name:
            obj, created = Category.objects.get_or_create(store=store, name=name)
            if created:
                obj.expiry_warning_days = expiry_warning_days
                obj.save(update_fields=['expiry_warning_days'])
        return redirect('inventory:category_list', store_slug=store.slug)
    categories = Category.objects.filter(store=store)
    existing_names = set(categories.values_list('name', flat=True))
    return render(request, 'inventory/category_list.html', {
        'store': store, 'categories': categories,
        'standard_categories': [c for c in STANDARD_RETAIL_CATEGORIES if c not in existing_names],
    })


@login_required
def category_form(request, store_slug):
    return category_list(request, store_slug)


@login_required
def package_list(request, store_slug):
    store = get_store(store_slug, request.user)
    packages = Package.objects.filter(store=store).prefetch_related('items__product')
    return render(request, 'inventory/package_list.html', {
        'store': store, 'packages': packages,
    })


@login_required
def package_form(request, store_slug, pk=None):
    store = get_store(store_slug, request.user)
    package = get_object_or_404(Package, pk=pk, store=store) if pk else None
    products = Product.objects.filter(store=store, is_active=True)

    if request.method == 'POST':
        data = request.POST
        if package is None:
            package = Package(store=store)
        package.name = data['name']
        package.description = data.get('description', '')
        package.package_price = data['package_price']
        package.save()

        # Clear old items and add new
        package.items.all().delete()
        product_ids = data.getlist('item_product')
        quantities = data.getlist('item_qty')
        for pid, qty in zip(product_ids, quantities):
            if pid and qty:
                PackageItem.objects.create(
                    package=package,
                    product_id=pid,
                    quantity=int(qty),
                )
        return redirect('inventory:package_list', store_slug=store.slug)

    return render(request, 'inventory/package_form.html', {
        'store': store, 'package': package, 'products': products,
    })


@login_required
def stock_overview(request, store_slug):
    from django.utils import timezone
    store = get_store(store_slug, request.user)
    products = Product.objects.filter(store=store, is_active=True).select_related('category').order_by('stock_qty')
    low = products.filter(stock_qty__lte=F('reorder_level'), stock_qty__gt=0)
    out = products.filter(stock_qty__lte=0)
    today = timezone.now().date()
    from datetime import timedelta as td
    expiring_soon = products.filter(
        expiry_date__isnull=False,
        expiry_date__gte=today,
        expiry_date__lte=today + td(days=30),
    ).order_by('expiry_date')
    expired = products.filter(expiry_date__isnull=False, expiry_date__lt=today)
    return render(request, 'inventory/stock_overview.html', {
        'store': store, 'products': products,
        'low_stock': low, 'out_of_stock': out,
        'expiring_soon': expiring_soon, 'expired': expired,
        'today': today,
    })


@login_required
def api_products(request, store_slug):
    store = get_store(store_slug, request.user)
    q = request.GET.get('q', '')
    products = Product.objects.filter(store=store, is_active=True)
    if q:
        products = products.filter(Q(name__icontains=q) | Q(sku__icontains=q))
    data = [{
        'id': str(p.id), 'name': p.name, 'sku': p.sku,
        'unit_price': str(p.unit_price), 'stock_qty': p.stock_qty,
        'unit_label': p.unit_label,
    } for p in products[:50]]
    return JsonResponse(data, safe=False)


@login_required
def supplier_list(request, store_slug):
    store = get_store(store_slug, request.user)
    suppliers = Supplier.objects.filter(store=store)
    total_owed = suppliers.filter(ownership='external').aggregate(t=Sum('outstanding_balance'))['t'] or 0
    total_invested = suppliers.filter(ownership='store_owned').aggregate(t=Sum('outstanding_balance'))['t'] or 0
    return render(request, 'inventory/supplier_list.html', {
        'store': store, 'suppliers': suppliers,
        'total_owed': total_owed, 'total_invested': total_invested,
    })


@login_required
def supplier_form(request, store_slug, pk=None):
    store = get_store(store_slug, request.user)
    supplier = get_object_or_404(Supplier, pk=pk, store=store) if pk else None

    if request.method == 'POST':
        data = request.POST
        if supplier is None:
            supplier = Supplier(store=store)
        supplier.name = data['name']
        supplier.contact_person = data.get('contact_person', '')
        supplier.phone = data.get('phone', '')
        supplier.email = data.get('email', '')
        supplier.address = data.get('address', '')
        supplier.notes = data.get('notes', '')
        supplier.ownership = data.get('ownership', 'external')
        supplier.save()
        messages.success(request, f'Supplier "{supplier.name}" saved.')
        return redirect('inventory:supplier_detail', store_slug=store.slug, pk=supplier.pk)

    return render(request, 'inventory/supplier_form.html', {
        'store': store, 'supplier': supplier,
    })


@login_required
def supplier_detail(request, store_slug, pk):
    store = get_store(store_slug, request.user)
    supplier = get_object_or_404(Supplier, pk=pk, store=store)
    transactions = supplier.transactions.all()[:50]
    return render(request, 'inventory/supplier_detail.html', {
        'store': store, 'supplier': supplier, 'transactions': transactions,
        'today': now().date(),
    })


@login_required
def supplier_transact(request, store_slug, pk):
    store = get_store(store_slug, request.user)
    supplier = get_object_or_404(Supplier, pk=pk, store=store)

    if request.method == 'POST':
        tx_type = request.POST['tx_type']
        amount = request.POST['amount']
        description = request.POST.get('description', '')
        date = request.POST.get('date') or now().date()
        SupplierTransaction.objects.create(
            supplier=supplier, tx_type=tx_type,
            amount=amount, description=description, date=date,
        )
        messages.success(request, 'Transaction recorded.')
    return redirect('inventory:supplier_detail', store_slug=store.slug, pk=pk)


@login_required
def supplier_toggle(request, store_slug, pk):
    store = get_store(store_slug, request.user)
    supplier = get_object_or_404(Supplier, pk=pk, store=store)
    supplier.is_active = not supplier.is_active
    supplier.save(update_fields=['is_active'])
    return redirect('inventory:supplier_list', store_slug=store.slug)


@login_required
def barcode_print(request, store_slug, pk):
    store = get_store(store_slug, request.user)
    product = get_object_or_404(Product, pk=pk, store=store)
    qty = int(request.GET.get('qty', 1))
    return render(request, 'inventory/barcode_print.html', {
        'store': store, 'product': product, 'qty': range(qty),
    })


@login_required
def api_packages(request, store_slug):
    store = get_store(store_slug, request.user)
    packages = Package.objects.filter(store=store, is_active=True).prefetch_related('items__product')
    data = [{
        'id': str(p.id), 'name': p.name,
        'package_price': str(p.package_price),
        'items': [{'product': i.product.name, 'qty': i.quantity} for i in p.items.all()],
    } for p in packages]
    return JsonResponse(data, safe=False)
