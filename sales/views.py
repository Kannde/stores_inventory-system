import json
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.db import transaction
from core.access import require_store_permission
from core.views import get_store
from core.models import StoreSettings, StoreStaff
from inventory.models import Product, Package, StockMovement
from .models import CreditAccount, CreditPayment, Sale, SaleItem


@login_required
def sale_list(request, store_slug):
    store = get_store(store_slug, request.user)
    require_store_permission(request.user, store, 'sell')
    sales = Sale.objects.filter(store=store).select_related('staff')[:50]
    return render(request, 'sales/sale_list.html', {'store': store, 'sales': sales})


@login_required
def new_sale(request, store_slug):
    store = get_store(store_slug, request.user)
    require_store_permission(request.user, store, 'sell')
    staff = StoreStaff.objects.filter(store=store, is_active=True, role__in=['sales', 'manager'])

    # Auto-detect current user's staff profile
    current_staff = None
    try:
        current_staff = StoreStaff.objects.get(store=store, user=request.user)
    except StoreStaff.DoesNotExist:
        pass

    products = Product.objects.filter(store=store, is_active=True).prefetch_related('images').order_by('name')
    packages = Package.objects.filter(store=store, is_active=True).prefetch_related('items__product').order_by('name')

    products_data = []
    for p in products:
        first_img = p.images.first()
        products_data.append({
            'id': str(p.id), 'name': p.name, 'sku': p.sku,
            'unit_price': str(p.unit_price), 'stock_qty': p.stock_qty,
            'unit_label': p.unit_label,
            'barcode': p.barcode,
            'image_url': first_img.image.url if first_img else None,
        })

    packages_data = [{
        'id': str(p.id), 'name': p.name,
        'package_price': str(p.package_price),
        'items': [{'product': i.product.name, 'qty': i.quantity} for i in p.items.all()],
    } for p in packages]

    store_settings, _ = StoreSettings.objects.get_or_create(store=store)

    return render(request, 'sales/new_sale.html', {
        'store': store,
        'staff': staff,
        'current_staff': current_staff,
        'products_json': json.dumps(products_data),
        'packages_json': json.dumps(packages_data),
        'allow_partial': store_settings.allow_partial_payment,
        'allow_credit': store_settings.allow_credit,
        'min_deposit_percent': store_settings.min_deposit_percent,
        'skroda_enabled': store_settings.skroda_enabled,
    })


@login_required
def sale_detail(request, store_slug, pk):
    store = get_store(store_slug, request.user)
    require_store_permission(request.user, store, 'sell')
    sale = get_object_or_404(Sale, pk=pk, store=store)
    return render(request, 'sales/sale_detail.html', {'store': store, 'sale': sale})


@login_required
def sale_receipt(request, store_slug, pk):
    store = get_store(store_slug, request.user)
    require_store_permission(request.user, store, 'sell')
    sale = get_object_or_404(Sale, pk=pk, store=store)
    return render(request, 'sales/receipt.html', {'store': store, 'sale': sale})


@login_required
@csrf_exempt
@require_POST
def api_checkout(request, store_slug):
    store = get_store(store_slug, request.user)
    require_store_permission(request.user, store, 'sell')
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
    customer_name = data.get('customer_name', '')
    customer_phone = data.get('customer_phone', '')

    store_settings, _ = StoreSettings.objects.get_or_create(store=store)

    # Escrow payments start as pending_payment; stock is held but sale not yet finalised
    initial_status = 'pending_payment' if payment_method == 'escrow' else 'completed'

    with transaction.atomic():
        sale = Sale(
            store=store,
            payment_method=payment_method,
            status=initial_status,
            amount_paid=0 if payment_method == 'escrow' else amount_paid,
            customer_name=customer_name,
            customer_phone=customer_phone,
            notes=data.get('notes', ''),
        )
        if staff_id:
            try:
                sale.staff = StoreStaff.objects.get(pk=staff_id, store=store)
            except StoreStaff.DoesNotExist:
                pass
        sale.save()

        total = 0
        item_names = []
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
            item_names.append(item_name)

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
        sale.change_given = 0 if payment_method == 'escrow' else max(0, float(amount_paid) - total)
        sale.save(update_fields=['total_amount', 'change_given'])

        if payment_method in ('credit', 'mixed') and customer_name:
            CreditAccount.objects.create(
                sale=sale,
                store=store,
                customer_name=customer_name,
                customer_phone=customer_phone,
                total_amount=total,
                amount_paid=float(amount_paid),
            )

    # Skroda escrow: create transaction and redirect buyer to hosted checkout
    if payment_method == 'escrow':
        if not store_settings.skroda_enabled or not store_settings.skroda_secret_key:
            sale.status = 'refunded'
            sale.save(update_fields=['status'])
            return JsonResponse({'error': 'Escrow payments are not configured for this store.'}, status=400)

        from payments.service import create_transaction
        from payments.models import SkrodaTransaction

        title = ', '.join(item_names[:3]) + (' & more' if len(item_names) > 3 else '')
        currency = store.currency_symbol if store.currency_symbol in ('GHS', 'USD', 'NGN') else 'GHS'
        seller_phone = store_settings.skroda_seller_phone or store.phone

        if not seller_phone:
            sale.status = 'refunded'
            sale.save(update_fields=['status'])
            return JsonResponse({'error': 'Skroda seller phone not configured. Set it in Store Settings → Skroda Escrow Payments.'}, status=400)

        success_url = request.build_absolute_uri(
            f'/s/{store.slug}/payments/skroda/{sale.id}/success/'
        )
        cancel_url = request.build_absolute_uri(
            f'/s/{store.slug}/payments/skroda/{sale.id}/cancelled/'
        )

        ok, txn_data = create_transaction(
            store_settings.skroda_secret_key,
            title=title,
            amount=total,
            currency=currency,
            seller_phone=seller_phone,
            seller_name=store.name,
            buyer_phone=customer_phone or None,
            buyer_name=customer_name or None,
            partner_reference=str(sale.id),
            fee_paid_by=store_settings.skroda_fee_paid_by,
            delivery_mode=store_settings.skroda_delivery_mode,
            success_url=success_url,
            cancel_url=cancel_url,
        )
        if not ok:
            sale.status = 'refunded'
            sale.save(update_fields=['status'])
            return JsonResponse({'error': txn_data.get('error', 'Failed to create escrow transaction.')}, status=502)

        checkout_url = txn_data.get('checkout_url', '')
        if not checkout_url or not checkout_url.startswith('https://skroda.com/pay/cs_'):
            sale.status = 'refunded'
            sale.save(update_fields=['status'])
            return JsonResponse({'error': 'Invalid checkout URL returned by Skroda.'}, status=502)

        SkrodaTransaction.objects.create(
            sale=sale,
            store=store,
            skroda_id=txn_data['id'],
            reference_code=txn_data.get('reference_code', ''),
            status=txn_data.get('status', 'draft'),
            delivery_mode=txn_data.get('delivery_mode', store_settings.skroda_delivery_mode),
            amount=total,
            checkout_url=checkout_url,
            invite_link=txn_data.get('invite_link', ''),
        )

        return JsonResponse({
            'success': True,
            'escrow': True,
            'sale_id': str(sale.id),
            'receipt_number': sale.receipt_number,
            'total': str(sale.total_amount),
            'checkout_url': checkout_url,
        })

    return JsonResponse({
        'success': True,
        'sale_id': str(sale.id),
        'receipt_number': sale.receipt_number,
        'total': str(sale.total_amount),
        'change': str(sale.change_given),
    })


@login_required
def credit_list(request, store_slug):
    store = get_store(store_slug, request.user)
    require_store_permission(request.user, store, 'manage_credit')
    credits = CreditAccount.objects.filter(store=store).select_related('sale').order_by('-created_at')
    unsettled = credits.filter(is_settled=False)
    total_outstanding = sum(c.balance_due for c in unsettled)
    return render(request, 'sales/credit_list.html', {
        'store': store, 'credits': credits,
        'total_outstanding': total_outstanding,
    })


@login_required
def credit_payment(request, store_slug, pk):
    store = get_store(store_slug, request.user)
    require_store_permission(request.user, store, 'manage_credit')
    credit = get_object_or_404(CreditAccount, pk=pk, store=store)
    if request.method == 'POST':
        amount = request.POST.get('amount')
        notes = request.POST.get('notes', '')
        date = request.POST.get('date') or __import__('django.utils.timezone', fromlist=['now']).now().date()
        if amount:
            from django.utils import timezone
            CreditPayment.objects.create(
                credit=credit,
                amount=amount,
                notes=notes,
                date=request.POST.get('date') or timezone.now().date(),
            )
    return redirect('sales:credit_list', store_slug=store.slug)
