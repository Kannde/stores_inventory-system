import json
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.db.models import F, Q
from core.views import get_store
from .models import Category, Product, ProductImage, Package, PackageItem, StockMovement


def product_list(request, store_slug):
    store = get_store(store_slug)
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


def product_form(request, store_slug, pk=None):
    store = get_store(store_slug)
    product = get_object_or_404(Product, pk=pk, store=store) if pk else None
    categories = Category.objects.filter(store=store)

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
        cat_id = data.get('category')
        product.category_id = cat_id if cat_id else None
        product.save()

        # Handle images
        for f in request.FILES.getlist('images'):
            ProductImage.objects.create(product=product, image=f)

        return redirect('inventory:product_list', store_slug=store.slug)

    return render(request, 'inventory/product_form.html', {
        'store': store, 'product': product, 'categories': categories,
    })


def stock_adjust(request, store_slug, pk):
    store = get_store(store_slug)
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


def category_list(request, store_slug):
    store = get_store(store_slug)
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        if name:
            Category.objects.get_or_create(store=store, name=name)
        return redirect('inventory:category_list', store_slug=store.slug)
    categories = Category.objects.filter(store=store)
    return render(request, 'inventory/category_list.html', {
        'store': store, 'categories': categories,
    })


def category_form(request, store_slug):
    return category_list(request, store_slug)


def package_list(request, store_slug):
    store = get_store(store_slug)
    packages = Package.objects.filter(store=store).prefetch_related('items__product')
    return render(request, 'inventory/package_list.html', {
        'store': store, 'packages': packages,
    })


def package_form(request, store_slug, pk=None):
    store = get_store(store_slug)
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


def stock_overview(request, store_slug):
    store = get_store(store_slug)
    products = Product.objects.filter(store=store, is_active=True).order_by('stock_qty')
    low = products.filter(stock_qty__lte=F('reorder_level'), stock_qty__gt=0)
    out = products.filter(stock_qty__lte=0)
    return render(request, 'inventory/stock_overview.html', {
        'store': store, 'products': products, 'low_stock': low, 'out_of_stock': out,
    })


def api_products(request, store_slug):
    store = get_store(store_slug)
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


def api_packages(request, store_slug):
    store = get_store(store_slug)
    packages = Package.objects.filter(store=store, is_active=True).prefetch_related('items__product')
    data = [{
        'id': str(p.id), 'name': p.name,
        'package_price': str(p.package_price),
        'items': [{'product': i.product.name, 'qty': i.quantity} for i in p.items.all()],
    } for p in packages]
    return JsonResponse(data, safe=False)
