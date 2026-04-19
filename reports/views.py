import json
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import DecimalField, ExpressionWrapper, F, Sum
from django.db.models.functions import TruncDate
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone

from core.views import get_store
from core.date_filter import resolve_period, parse_entity_filters
from core.models import StoreStaff
from expenses.models import Expense
from inventory.models import Category, Product
from sales.models import Sale, SaleItem


@login_required
def dashboard(request, store_slug):
    store = get_store(store_slug, request.user)
    today = timezone.now().date()

    pf = resolve_period(request, today, default='this_month')
    ef = parse_entity_filters(request)
    start_date, end_date = pf['start_date'], pf['end_date']
    active_staff_id = ef['active_staff_id']
    active_category_id = ef['active_category_id']
    active_product_id = ef['active_product_id']

    # Base item filter (always used for COGS, top products, category breakdown)
    item_q = {
        'sale__store': store,
        'sale__created_at__date__gte': start_date,
        'sale__created_at__date__lte': end_date,
        'sale__status': 'completed',
        'product__isnull': False,
    }
    if active_staff_id:
        item_q['sale__staff__pk'] = active_staff_id
    if active_category_id:
        item_q['product__category__pk'] = active_category_id
    if active_product_id:
        item_q['product__pk'] = active_product_id

    sale_items = SaleItem.objects.filter(**item_q).select_related('product', 'product__category')

    # Revenue — use item line_totals when product/category filtered, else sale totals
    if active_category_id or active_product_id:
        total_revenue = sale_items.aggregate(t=Sum('line_total'))['t'] or 0
        total_sales = sale_items.values('sale').distinct().count()
    else:
        sale_q = {
            'store': store,
            'created_at__date__gte': start_date,
            'created_at__date__lte': end_date,
            'status': 'completed',
        }
        if active_staff_id:
            sale_q['staff__pk'] = active_staff_id
        sales_qs = Sale.objects.filter(**sale_q)
        total_revenue = sales_qs.aggregate(t=Sum('total_amount'))['t'] or 0
        total_sales = sales_qs.count()

    total_revenue = float(total_revenue)

    # COGS via DB aggregate (efficient regardless of period length)
    total_cogs = float(
        SaleItem.objects.filter(**item_q).aggregate(
            total=Sum(ExpressionWrapper(F('quantity') * F('product__cost_price'), output_field=DecimalField()))
        )['total'] or 0
    )
    gross_profit = total_revenue - total_cogs
    margin_pct = (gross_profit / total_revenue * 100) if total_revenue else 0

    # Operating expenses (date-filtered only, not by staff/category/product)
    exp_q = {'store': store, 'date__gte': start_date, 'date__lte': end_date}
    total_expenses = float(Expense.objects.filter(**exp_q).aggregate(t=Sum('amount'))['t'] or 0)
    expenses_by_cat = list(
        Expense.objects.filter(**exp_q).values('category').annotate(total=Sum('amount')).order_by('-total')
    )
    net_profit = gross_profit - total_expenses
    net_margin_pct = (net_profit / total_revenue * 100) if total_revenue else 0

    # Top products
    top_products_qs = sale_items.values('product__name', 'product__cost_price').annotate(
        total_qty=Sum('quantity'),
        total_rev=Sum('line_total'),
    ).order_by('-total_rev')[:10]

    top_products = []
    for p in top_products_qs:
        rev = float(p['total_rev'])
        cogs = float(p['product__cost_price']) * int(p['total_qty'])
        top_products.append({**p, 'total_rev': rev, 'cogs': cogs, 'profit': rev - cogs})

    category_breakdown = list(
        sale_items.filter(product__category__isnull=False)
        .values('product__category__name')
        .annotate(total_rev=Sum('line_total'), total_qty=Sum('quantity'))
        .order_by('-total_rev')[:10]
    )

    # Daily trend — 3 DB queries regardless of range length
    daily_rev_map = {}
    if active_category_id or active_product_id:
        for row in (
            SaleItem.objects.filter(**item_q)
            .annotate(day=TruncDate('sale__created_at'))
            .values('day').annotate(rev=Sum('line_total'))
        ):
            daily_rev_map[row['day']] = float(row['rev'] or 0)
    else:
        _sq = {
            'store': store, 'created_at__date__gte': start_date,
            'created_at__date__lte': end_date, 'status': 'completed',
        }
        if active_staff_id:
            _sq['staff__pk'] = active_staff_id
        for row in (
            Sale.objects.filter(**_sq)
            .annotate(day=TruncDate('created_at'))
            .values('day').annotate(rev=Sum('total_amount'))
        ):
            daily_rev_map[row['day']] = float(row['rev'] or 0)

    daily_cogs_map = {}
    for row in (
        SaleItem.objects.filter(**item_q)
        .annotate(day=TruncDate('sale__created_at'))
        .values('day')
        .annotate(cogs=Sum(ExpressionWrapper(F('quantity') * F('product__cost_price'), output_field=DecimalField())))
    ):
        daily_cogs_map[row['day']] = float(row['cogs'] or 0)

    daily_exp_map = {}
    for row in Expense.objects.filter(**exp_q).values('date').annotate(exp=Sum('amount')):
        daily_exp_map[row['date']] = float(row['exp'] or 0)

    delta = (end_date - start_date).days + 1
    daily_data = []
    for i in range(delta):
        d = start_date + timedelta(days=i)
        rev = daily_rev_map.get(d, 0)
        cogs = daily_cogs_map.get(d, 0)
        exp = daily_exp_map.get(d, 0)
        daily_data.append({
            'date': d.strftime('%b %d'),
            'revenue': rev,
            'cogs': round(cogs, 2),
            'expenses': round(exp, 2),
            'profit': round(rev - cogs - exp, 2),
        })

    # Filter dropdown data
    filter_staff = StoreStaff.objects.filter(store=store, is_active=True).order_by('name')
    filter_categories = Category.objects.filter(store=store).order_by('name')
    filter_products = Product.objects.filter(store=store, is_active=True).order_by('name')

    context = {
        'store': store,
        'total_revenue': total_revenue,
        'total_sales': total_sales,
        'total_cogs': round(total_cogs, 2),
        'gross_profit': round(gross_profit, 2),
        'margin_pct': round(margin_pct, 1),
        'total_expenses': round(total_expenses, 2),
        'expenses_by_cat': expenses_by_cat,
        'net_profit': round(net_profit, 2),
        'net_margin_pct': round(net_margin_pct, 1),
        'avg_sale': total_revenue / max(total_sales, 1),
        'top_products': top_products,
        'category_breakdown': category_breakdown,
        'daily_data_json': json.dumps(daily_data),
        'filter_staff': filter_staff,
        'filter_categories': filter_categories,
        'filter_products': filter_products,
        **pf,
        **ef,
    }
    return render(request, 'reports/dashboard.html', context)


@login_required
def api_sales_chart(request, store_slug):
    store = get_store(store_slug, request.user)
    days = int(request.GET.get('days', 7))
    today = timezone.now().date()
    data = []
    for i in range(days - 1, -1, -1):
        d = today - timedelta(days=i)
        rev = Sale.objects.filter(
            store=store, created_at__date=d
        ).aggregate(t=Sum('total_amount'))['t'] or 0
        count = Sale.objects.filter(store=store, created_at__date=d).count()
        data.append({'date': d.strftime('%b %d'), 'revenue': float(rev), 'count': count})
    return JsonResponse(data, safe=False)


@login_required
def api_top_products(request, store_slug):
    store = get_store(store_slug, request.user)
    days = int(request.GET.get('days', 7))
    start = timezone.now().date() - timedelta(days=days)
    top = SaleItem.objects.filter(
        sale__store=store, sale__created_at__date__gte=start,
        product__isnull=False,
    ).values('product__name').annotate(
        total_qty=Sum('quantity'),
        total_rev=Sum('line_total'),
    ).order_by('-total_rev')[:10]
    return JsonResponse(list(top), safe=False)
