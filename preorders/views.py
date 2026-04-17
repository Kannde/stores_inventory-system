import json
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from core.views import get_store
from core.models import StoreSettings
from inventory.models import Product
from .models import PreOrder, PreOrderItem


def preorder_form(request, store_slug):
    store = get_store(store_slug)
    store_settings, _ = StoreSettings.objects.get_or_create(store=store)

    if not store_settings.preorder_enabled:
        return render(request, 'preorders/preorder_disabled.html', {'store': store})

    products = Product.objects.filter(store=store, is_active=True, available_for_preorder=True).prefetch_related('images').order_by('name')
    products_data = []
    for p in products:
        first_img = p.images.first()
        products_data.append({
            'id': str(p.id), 'name': p.name, 'sku': p.sku,
            'unit_price': str(p.unit_price), 'stock_qty': p.stock_qty,
            'unit_label': p.unit_label,
            'image_url': first_img.image.url if first_img else None,
        })

    if request.method == 'POST':
        items_json = request.POST.get('items_json', '[]')
        try:
            items = json.loads(items_json)
        except (json.JSONDecodeError, ValueError):
            items = []

        if not items:
            return render(request, 'preorders/preorder_form.html', {
                'store': store, 'store_settings': store_settings,
                'products_json': json.dumps(products_data),
                'error': 'Please add at least one item to your order.',
            })

        po = PreOrder.objects.create(
            store=store,
            customer_name=request.POST['customer_name'],
            customer_phone=request.POST['customer_phone'],
            customer_whatsapp=request.POST.get('customer_whatsapp', ''),
            customer_city=request.POST.get('customer_city', ''),
            customer_email=request.POST.get('customer_email', ''),
            notes=request.POST.get('notes', ''),
            desired_date=request.POST.get('desired_date') or None,
        )

        for item in items:
            product = None
            if item.get('id'):
                try:
                    product = Product.objects.get(pk=item['id'], store=store)
                except Product.DoesNotExist:
                    pass
            PreOrderItem.objects.create(
                preorder=po,
                product=product,
                item_description=item.get('name', ''),
                quantity=int(item.get('quantity', 1)),
                unit_label=item.get('unit_label', 'unit'),
                unit_price=item.get('unit_price', 0),
            )

        # WhatsApp notification if store has a number configured
        whatsapp_url = None
        if store_settings.preorder_whatsapp_number:
            msg = f"New preorder from {po.customer_name} ({po.customer_phone}) at {store.name}. {len(items)} item(s)."
            import urllib.parse
            whatsapp_url = f"https://wa.me/{store_settings.preorder_whatsapp_number}?text={urllib.parse.quote(msg)}"

        return redirect('preorders:preorder_success', store_slug=store.slug)

    return render(request, 'preorders/preorder_form.html', {
        'store': store,
        'store_settings': store_settings,
        'products_json': json.dumps(products_data),
    })


def preorder_success(request, store_slug):
    store = get_store(store_slug)
    return render(request, 'preorders/preorder_success.html', {'store': store})


@login_required
def preorder_list(request, store_slug):
    store = get_store(store_slug, request.user)
    status = request.GET.get('status', 'pending')
    preorders = PreOrder.objects.filter(store=store)
    if status != 'all':
        preorders = preorders.filter(status=status)
    store_settings, _ = StoreSettings.objects.get_or_create(store=store)
    return render(request, 'preorders/preorder_list.html', {
        'store': store, 'preorders': preorders, 'current_status': status,
        'store_settings': store_settings,
    })


@login_required
def preorder_detail(request, store_slug, pk):
    store = get_store(store_slug, request.user)
    po = get_object_or_404(PreOrder, pk=pk, store=store)
    return render(request, 'preorders/preorder_detail.html', {'store': store, 'preorder': po})


@login_required
def preorder_status(request, store_slug, pk):
    store = get_store(store_slug, request.user)
    po = get_object_or_404(PreOrder, pk=pk, store=store)
    if request.method == 'POST':
        new_status = request.POST.get('status')
        if new_status in dict(PreOrder.STATUS_CHOICES):
            po.status = new_status
            po.staff_notes = request.POST.get('staff_notes', po.staff_notes)
            po.save(update_fields=['status', 'staff_notes'])
    return redirect('preorders:preorder_detail', store_slug=store.slug, pk=po.pk)
