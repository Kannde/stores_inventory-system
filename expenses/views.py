import json
from datetime import date
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db.models import Sum
from django.utils import timezone

from core.access import require_store_permission
from core.views import get_store
from core.models import StoreStaff
from inventory.models import Product
from shipments.models import Shipment
from .models import Expense


@login_required
def expense_list(request, store_slug):
    store = get_store(store_slug, request.user)
    require_store_permission(request.user, store, 'view_expenses')

    # Filter controls
    category = request.GET.get('cat', '')
    month    = request.GET.get('month', timezone.now().strftime('%Y-%m'))

    try:
        year, mon = int(month.split('-')[0]), int(month.split('-')[1])
    except Exception:
        year, mon = timezone.now().year, timezone.now().month

    qs = Expense.objects.filter(store=store, date__year=year, date__month=mon)
    if category:
        qs = qs.filter(category=category)

    total = qs.aggregate(t=Sum('amount'))['t'] or 0
    by_category = (
        Expense.objects.filter(store=store, date__year=year, date__month=mon)
        .values('category')
        .annotate(total=Sum('amount'))
        .order_by('-total')
    )

    staff = StoreStaff.objects.filter(store=store, is_active=True)
    products = Product.objects.filter(store=store, is_active=True).values('id', 'name', 'cost_price', 'unit_label')
    shipments = Shipment.objects.filter(store=store).order_by('-created_at')

    return render(request, 'expenses/expense_list.html', {
        'store': store,
        'expenses': qs.select_related('recorded_by', 'product', 'shipment'),
        'total': total,
        'by_category': by_category,
        'category_choices': Expense.CATEGORY_CHOICES,
        'selected_cat': category,
        'month': month,
        'staff': staff,
        'products_json': json.dumps([
            {'id': str(p['id']), 'name': p['name'],
             'cost_price': str(p['cost_price']), 'unit_label': p['unit_label']}
            for p in products
        ]),
        'shipments_json': json.dumps([
            {'id': str(s.id), 'tracking_number': s.tracking_number, 'shipping_company': s.shipping_company}
            for s in shipments
        ]),
    })


@login_required
@require_POST
def expense_add(request, store_slug):
    store = get_store(store_slug, request.user)
    require_store_permission(request.user, store, 'view_expenses')

    category    = request.POST.get('category', 'other')
    amount      = request.POST.get('amount', '').strip()
    description = request.POST.get('description', '').strip()
    exp_date    = request.POST.get('date') or timezone.now().date()
    staff_id    = request.POST.get('recorded_by', '')
    product_id  = request.POST.get('product_id', '')
    shipment_id = request.POST.get('shipment_id', '')
    product_qty = int(request.POST.get('product_qty', 1) or 1)
    next_url    = request.POST.get('next', '').strip()

    if not amount:
        return redirect('expenses:expense_list', store_slug=store_slug)

    expense = Expense(
        store=store,
        category=category,
        amount=amount,
        description=description,
        date=exp_date,
        product_qty=product_qty,
    )
    if staff_id:
        try:
            expense.recorded_by = StoreStaff.objects.get(pk=staff_id, store=store)
        except StoreStaff.DoesNotExist:
            pass
    if product_id and category in ('breakage', 'expiry'):
        try:
            expense.product = Product.objects.get(pk=product_id, store=store)
        except Product.DoesNotExist:
            pass
    if shipment_id:
        try:
            expense.shipment = Shipment.objects.get(pk=shipment_id, store=store)
        except Shipment.DoesNotExist:
            pass
    expense.save()

    if next_url:
        return redirect(next_url)

    month = str(exp_date)[:7] if isinstance(exp_date, str) else exp_date.strftime('%Y-%m')
    return redirect(f"{request.path.replace('/add', '')}?month={month}")


@login_required
@require_POST
def expense_delete(request, store_slug, pk):
    store = get_store(store_slug, request.user)
    require_store_permission(request.user, store, 'view_expenses')
    expense = get_object_or_404(Expense, pk=pk, store=store)
    month = expense.date.strftime('%Y-%m')
    expense.delete()
    return redirect(f"/s/{store_slug}/expenses/?month={month}")
