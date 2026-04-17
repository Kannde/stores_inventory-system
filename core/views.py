from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.db.models import Sum, Count, Q, F
from django.utils import timezone
from datetime import timedelta
from .models import Store, StoreStaff


def get_store(store_slug):
    return get_object_or_404(Store, slug=store_slug, is_active=True)


def home(request):
    stores = Store.objects.filter(is_active=True)
    return render(request, 'core/home.html', {'stores': stores})


def store_dashboard(request, store_slug):
    store = get_store(store_slug)
    today = timezone.now().date()
    week_ago = today - timedelta(days=7)

    from sales.models import Sale
    from inventory.models import Product
    from preorders.models import PreOrder

    today_sales = Sale.objects.filter(store=store, created_at__date=today)
    week_sales = Sale.objects.filter(store=store, created_at__date__gte=week_ago)

    context = {
        'store': store,
        'today_revenue': today_sales.aggregate(t=Sum('total_amount'))['t'] or 0,
        'today_count': today_sales.count(),
        'week_revenue': week_sales.aggregate(t=Sum('total_amount'))['t'] or 0,
        'week_count': week_sales.count(),
        'total_products': Product.objects.filter(store=store, is_active=True).count(),
        'low_stock': Product.objects.filter(store=store, is_active=True, stock_qty__lte=F('reorder_level')).count(),
        'out_of_stock': Product.objects.filter(store=store, is_active=True, stock_qty__lte=0).count(),
        'pending_preorders': PreOrder.objects.filter(store=store, status='pending').count(),
        'recent_sales': Sale.objects.filter(store=store).select_related('staff')[:5],
        'staff_count': StoreStaff.objects.filter(store=store, is_active=True).count(),
    }
    return render(request, 'core/dashboard.html', context)


def staff_list(request, store_slug):
    store = get_store(store_slug)
    staff = StoreStaff.objects.filter(store=store)
    return render(request, 'core/staff_list.html', {'store': store, 'staff': staff})


def staff_add(request, store_slug):
    store = get_store(store_slug)
    if request.method == 'POST':
        StoreStaff.objects.create(
            store=store,
            name=request.POST['name'],
            phone=request.POST.get('phone', ''),
            role=request.POST.get('role', 'sales'),
            pin=request.POST.get('pin', ''),
        )
        return redirect('core:staff_list', store_slug=store.slug)
    return render(request, 'core/staff_form.html', {'store': store, 'staff_member': None})


def staff_edit(request, store_slug, pk):
    store = get_store(store_slug)
    member = get_object_or_404(StoreStaff, pk=pk, store=store)
    if request.method == 'POST':
        member.name = request.POST['name']
        member.phone = request.POST.get('phone', '')
        member.role = request.POST.get('role', 'sales')
        member.pin = request.POST.get('pin', '')
        member.save()
        return redirect('core:staff_list', store_slug=store.slug)
    return render(request, 'core/staff_form.html', {'store': store, 'staff_member': member})


def staff_toggle(request, store_slug, pk):
    store = get_store(store_slug)
    member = get_object_or_404(StoreStaff, pk=pk, store=store)
    member.is_active = not member.is_active
    member.save(update_fields=['is_active'])
    return redirect('core:staff_list', store_slug=store.slug)
