import json
from datetime import timedelta
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.http import JsonResponse
from django.db.models import Sum, Count, F
from django.utils import timezone
from core.views import get_store
from sales.models import Sale, SaleItem
from inventory.models import Product


@login_required
def dashboard(request, store_slug):
    store = get_store(store_slug, request.user)
    today = timezone.now().date()
    period = request.GET.get('period', '7')
    days = int(period)
    start_date = today - timedelta(days=days)

    sales = Sale.objects.filter(store=store, created_at__date__gte=start_date)
    context = {
        'store': store,
        'period': period,
        'total_revenue': sales.aggregate(t=Sum('total_amount'))['t'] or 0,
        'total_sales': sales.count(),
        'avg_sale': (sales.aggregate(t=Sum('total_amount'))['t'] or 0) / max(sales.count(), 1),
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
