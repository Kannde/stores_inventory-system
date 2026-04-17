import json
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.db import transaction
from core.views import get_store
from core.models import StoreStaff
from inventory.models import Product, Package, StockMovement
from .models import Sale, SaleItem


@login_required
def sale_list(request, store_slug):
    store = get_store(store_slug, request.user)
    sales = Sale.objects.filter(store=store).select_related('staff')[:50]
    return render(request, 'sales/sale_list.html', {'store': store, 'sales': sales})


@login_required
def new_sale(request, store_slug):
    store = get_store(store_slug, request.user)
    staff = StoreStaff.objects.filter(store=store, is_active=True, role__in=['sales', 'manager'])

    products = Product.objects.filter(store=store, is_active=True).prefetch_related('images').order_by('name')
    packages = Package.objects.filter(store=store, is_active=True).prefetch_related('items__product').order_by('name')

    products_data = []
    for p in products:
        first_img = p.images.first()
        products_data.append({
            'id': str(p.id), 'name': p.name, 'sku': p.sku,
            'unit_price': str(p.unit_price), 'stock_qty': p.stock_qty,
            'unit_label': p.unit_label,
            'image_url': first_img.image.url if first_img else None,
        })

    packages_data = [{
        'id': str(p.id), 'name': p.name,
        'package_price': str(p.package_price),
        'items': [{'product': i.product.name, 'qty': i.quantity} for i in p.items.all()],
    } for p in packages]

    return render(request, 'sales/new_sale.html', {
        'store': store,
        'staff': staff,
        'products_json': json.dumps(products_data),
        'packages_json': json.dumps(packages_data),
    })


@login_required
def sale_detail(request, store_slug, pk):
    store = get_store(store_slug, request.user)
    sale = get_object_or_404(Sale, pk=pk, store=store)
    return render(request, 'sales/sale_detail.html', {'store': store, 'sale': sale})


@login_required
def sale_receipt(request, store_slug, pk):
    store = get_store(store_slug, request.user)
    sale = get_object_or_404(Sale, pk=pk, store=store)
    return render(request, 'sales/receipt.html', {'store': store, 'sale': sale})


@login_required
@csrf_exempt
@require_POST
def api_checkout(request, store_slug):
    store = get_store(store_slug, request.user)
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    items = data.get('items', [])
    if not items:
        return JsonResponse({'error': 'No items'}, status=400)

    staff_id = data.get('staff_id')
    payment_method = data.get('payment_method', 'cash')
    amount_paid = data.get('amount_paid', 0)

    with transaction.atomic():
        sale = Sale(
            store=store,
            payment_method=payment_method,
            amount_paid=amount_paid,
            notes=data.get('notes', ''),
        )
        if staff_id:
            try:
                sale.staff = StoreStaff.objects.get(pk=staff_id, store=store)
            except StoreStaff.DoesNotExist:
                pass
        sale.save()

        total = 0
        for item in items:
            item_type = item.get('type', 'product')
            qty = int(item.get('quantity', 1))
            unit_price = 0
            item_name = ''
            product = None
            package = None

            if item_type == 'product':
                product = get_object_or_404(Product, pk=item['id'], store=store)
                unit_price = float(item.get('unit_price', product.unit_price))
                item_name = product.name
                # Deduct stock
                product.stock_qty = max(0, product.stock_qty - qty)
                product.save(update_fields=['stock_qty'])
                StockMovement.objects.create(
                    product=product, movement_type='sale',
                    quantity=-qty, reference=str(sale.id),
                )
            elif item_type == 'package':
                package = get_object_or_404(Package, pk=item['id'], store=store)
                unit_price = float(item.get('unit_price', package.package_price))
                item_name = package.name
                # Deduct stock for each item in package
                for pi in package.items.select_related('product').all():
                    prod = pi.product
                    deduct = pi.quantity * qty
                    prod.stock_qty = max(0, prod.stock_qty - deduct)
                    prod.save(update_fields=['stock_qty'])
                    StockMovement.objects.create(
                        product=prod, movement_type='sale',
                        quantity=-deduct, reference=str(sale.id),
                    )

            line_total = qty * unit_price
            total += line_total

            SaleItem.objects.create(
                sale=sale,
                product=product,
                package=package,
                item_name=item_name,
                quantity=qty,
                unit_price=unit_price,
                line_total=line_total,
            )

        sale.total_amount = total
        sale.change_given = max(0, float(amount_paid) - total)
        sale.save(update_fields=['total_amount', 'change_given'])

    return JsonResponse({
        'success': True,
        'sale_id': str(sale.id),
        'receipt_number': sale.receipt_number,
        'total': str(sale.total_amount),
        'change': str(sale.change_given),
    })
