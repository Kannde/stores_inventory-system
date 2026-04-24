import json
import urllib.parse

from django.contrib.auth.decorators import login_required
from django.db.models import Prefetch, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from core.access import require_store_permission
from core.models import StoreSettings
from core.views import get_store
from inventory.models import Product, ProductImage
from .models import PreOrder, PreOrderItem


def _build_products_data(products):
    products_data = []
    for product in products:
        images = [img.image.url for img in product.images.all()]
        products_data.append({
            'id': str(product.id),
            'name': product.name,
            'sku': product.sku,
            'unit_price': str(product.unit_price),
            'stock_qty': product.stock_qty,
            'unit_label': product.unit_label,
            'image_url': images[0] if images else None,
            'image_urls': images,
            'lead_days': product.preorder_lead_days,
            'description': product.preorder_description_text,
            'color_options': product.color_option_list,
            'size_options': product.size_option_list,
        })
    return products_data


def _get_preorder_catalog(store, store_settings):
    products = Product.objects.filter(store=store, is_active=True)
    if not store_settings.preorder_all_products:
        products = products.filter(available_for_preorder=True)
    return products.prefetch_related(
        Prefetch('images', queryset=ProductImage.objects.order_by('sort_order', 'id'))
    ).order_by('name')


def preorder_form(request, store_slug):
    store = get_store(store_slug)
    store_settings, _ = StoreSettings.objects.get_or_create(store=store)

    if not store_settings.preorder_enabled:
        return render(request, 'preorders/preorder_disabled.html', {'store': store})

    products = _get_preorder_catalog(store, store_settings)
    products_data = _build_products_data(products)

    if request.method == 'POST':
        items_json = request.POST.get('items_json', '[]')
        try:
            items = json.loads(items_json)
        except (json.JSONDecodeError, ValueError):
            items = []

        if not items:
            return render(request, 'preorders/preorder_form.html', {
                'store': store,
                'store_settings': store_settings,
                'products_json': json.dumps(products_data),
                'error': 'Please add at least one item to your order.',
            })

        preorder = PreOrder.objects.create(
            store=store,
            customer_name=request.POST['customer_name'],
            customer_phone=request.POST['customer_phone'],
            customer_whatsapp=request.POST.get('customer_whatsapp', ''),
            customer_city=request.POST.get('customer_city', ''),
            customer_email=request.POST.get('customer_email', ''),
            notes=request.POST.get('notes', ''),
            desired_date=request.POST.get('desired_date') or None,
        )

        product_map = {
            str(product.id): product
            for product in products
        }

        for item in items:
            product = product_map.get(str(item.get('id', '')))
            selected_color = (item.get('selected_color') or '').strip()
            selected_size = (item.get('selected_size') or '').strip()
            try:
                quantity = max(int(item.get('quantity', 1)), 1)
            except (TypeError, ValueError):
                quantity = 1

            if product:
                if selected_color not in product.color_option_list:
                    selected_color = ''
                if selected_size not in product.size_option_list:
                    selected_size = ''

            PreOrderItem.objects.create(
                preorder=preorder,
                product=product,
                item_description=item.get('name', ''),
                quantity=quantity,
                unit_label=item.get('unit_label', 'unit'),
                unit_price=item.get('unit_price', 0),
                selected_color=selected_color,
                selected_size=selected_size,
            )

        return redirect(f"{reverse('preorders:preorder_success', args=[store.slug])}?order={preorder.pk}")

    return render(request, 'preorders/preorder_form.html', {
        'store': store,
        'store_settings': store_settings,
        'products_json': json.dumps(products_data),
    })


def preorder_success(request, store_slug):
    store = get_store(store_slug)
    preorder = None
    preorder_id = request.GET.get('order')
    if preorder_id:
        preorder = PreOrder.objects.filter(pk=preorder_id, store=store).first()
    return render(request, 'preorders/preorder_success.html', {'store': store, 'preorder': preorder})


@login_required
def preorder_list(request, store_slug):
    store = get_store(store_slug, request.user)
    require_store_permission(request.user, store, 'manage_preorders')
    status = request.GET.get('status', 'pending')
    q = request.GET.get('q', '').strip()

    preorders = PreOrder.objects.filter(store=store).prefetch_related('items')
    if status != 'all':
        preorders = preorders.filter(status=status)
    if q:
        preorders = preorders.filter(
            Q(customer_name__icontains=q)
            | Q(customer_phone__icontains=q)
            | Q(customer_whatsapp__icontains=q)
            | Q(pickup_code__icontains=q)
        )

    store_settings, _ = StoreSettings.objects.get_or_create(store=store)
    return render(request, 'preorders/preorder_list.html', {
        'store': store,
        'preorders': preorders,
        'current_status': status,
        'store_settings': store_settings,
        'q': q,
    })


@login_required
def preorder_detail(request, store_slug, pk):
    store = get_store(store_slug, request.user)
    require_store_permission(request.user, store, 'manage_preorders')
    preorder = get_object_or_404(
        PreOrder.objects.prefetch_related('items__product'),
        pk=pk,
        store=store,
    )
    estimated_total = sum(item.line_total for item in preorder.items.all())

    pickup_whatsapp_url = None
    if preorder.pickup_code_is_active and preorder.customer_whatsapp:
        message = (
            f"Hello {preorder.customer_name}, your preorder from {store.name} is ready for pickup. "
            f"Your pickup code is {preorder.pickup_code}. Please show this code in store."
        )
        pickup_whatsapp_url = (
            f"https://wa.me/{preorder.customer_whatsapp}?text={urllib.parse.quote(message)}"
        )

    return render(request, 'preorders/preorder_detail.html', {
        'store': store,
        'preorder': preorder,
        'estimated_total': estimated_total,
        'pickup_whatsapp_url': pickup_whatsapp_url,
    })


@login_required
def preorder_status(request, store_slug, pk):
    store = get_store(store_slug, request.user)
    require_store_permission(request.user, store, 'manage_preorders')
    preorder = get_object_or_404(PreOrder, pk=pk, store=store)
    if request.method == 'POST':
        new_status = request.POST.get('status')
        if new_status in dict(PreOrder.STATUS_CHOICES):
            preorder.status = new_status
            preorder.staff_notes = request.POST.get('staff_notes', preorder.staff_notes)

            if new_status == 'ready':
                preorder.activate_pickup_code()
            elif new_status == 'fulfilled':
                preorder.expire_pickup_code(used=True)
            elif new_status == 'cancelled':
                preorder.expire_pickup_code(used=False)
            elif preorder.pickup_code and preorder.status != 'ready':
                preorder.expire_pickup_code(used=False)

            preorder.save()

        if request.POST.get('return_to') == 'list':
            params = {'status': request.POST.get('return_status', 'ready')}
            q = request.POST.get('return_q', '').strip()
            if q:
                params['q'] = q
            return redirect(f"{reverse('preorders:preorder_list', args=[store.slug])}?{urllib.parse.urlencode(params)}")

    return redirect('preorders:preorder_detail', store_slug=store.slug, pk=preorder.pk)
