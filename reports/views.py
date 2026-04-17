import json
from datetime import timedelta
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.http import JsonResponse
from django.db.models import Sum, Count, F, DecimalField, ExpressionWrapper
from django.utils import timezone
from core.views import get_store
from sales.models import Sale, SaleItem
from inventory.models import Product, Category


@login_required
def dashboard(request, store_slug):
    store = get_store(store_slug, request.user)
    today = timezone.now().date()
    period = request.GET.get('period', '7')
    days = int(period)
    start_date = today - timedelta(days=days - 1)

    sales = Sale.objects.filter(store=store, created_at__date__gte=start_date, status='completed')
    sale_items = SaleItem.objects.filter(
        sale__store=store,
        sale__created_at__date__gte=start_date,
        sale__status='completed',
        product__isnull=False,
    ).select_related('product')

    total_revenue = sales.aggregate(t=Sum('total_amount'))['t'] or 0
    total_cogs = sum(
        float(si.quantity) * float(si.product.cost_price)
        for si in sale_items
    )
    gross_profit = float(total_revenue) - total_cogs
    margin_pct = (gross_profit / float(total_revenue) * 100) if total_revenue else 0

    top_products = sale_items.values('product__name', 'product__cost_price').annotate(
        total_qty=Sum('quantity'),
        total_rev=Sum('line_total'),
    ).order_by('-total_rev')[:10]

    top_products_enriched = []
    for p in top_products:
        rev = float(p['total_rev'])
        cogs = float(p['product__cost_price']) * int(p['total_qty'])
        top_products_enriched.append({
            **p,
            'total_rev': rev,
            'cogs': cogs,
            'profit': rev - cogs,
        })

    category_breakdown = sale_items.filter(
        product__category__isnull=False
    ).values('product__category__name').annotate(
        total_rev=Sum('line_total'),
        total_qty=Sum('quantity'),
    ).order_by('-total_rev')[:10]

    daily_data = []
    for i in range(days - 1, -1, -1):
        d = today - timedelta(days=i)
        day_sales = Sale.objects.filter(store=store, created_at__date=d, status='completed')
        day_items = SaleItem.objects.filter(
            sale__store=store, sale__created_at__date=d,
            sale__status='completed', product__isnull=False,
        ).select_related('product')
        rev = day_sales.aggregate(t=Sum('total_amount'))['t'] or 0
        cogs = sum(float(si.quantity) * float(si.product.cost_price) for si in day_items)
        daily_data.append({
            'date': d.strftime('%b %d'),
            'revenue': float(rev),
            'cogs': round(cogs, 2),
            'profit': round(float(rev) - cogs, 2),
        })

    context = {
        'store': store,
        'period': period,
        'start_date': start_date,
        'total_revenue': total_revenue,
        'total_sales': sales.count(),
        'total_cogs': round(total_cogs, 2),
        'gross_profit': round(gross_profit, 2),
        'margin_pct': round(margin_pct, 1),
        'avg_sale': float(total_revenue) / max(sales.count(), 1),
        'top_products': top_products_enriched,
        'category_breakdown': list(category_breakdown),
        'daily_data_json': json.dumps(daily_data),
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
