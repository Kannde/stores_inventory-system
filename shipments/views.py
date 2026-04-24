import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Prefetch, Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST
from django.utils import timezone

from core.access import require_store_permission
from core.views import get_store
from expenses.models import Expense
from inventory.models import Product, Supplier

from .models import Shipment, ShipmentPackage, ShipmentPackageItem


def _shipment_queryset(store):
    return Shipment.objects.filter(store=store).prefetch_related(
        Prefetch(
            'packages',
            queryset=ShipmentPackage.objects.select_related('supplier').prefetch_related(
                Prefetch(
                    'items',
                    queryset=ShipmentPackageItem.objects.select_related('product', 'supplier'),
                )
            ),
        ),
        'history',
    )


def _serialize_shipment(shipment):
    return {
        'id': str(shipment.id),
        'tracking_number': shipment.tracking_number,
        'shipping_company': shipment.shipping_company,
        'method': shipment.method,
        'status': shipment.status,
        'origin': shipment.origin,
        'destination': shipment.destination,
        'departure_date': shipment.departure_date.isoformat() if shipment.departure_date else None,
        'estimated_arrival': shipment.estimated_arrival.isoformat() if shipment.estimated_arrival else None,
        'actual_arrival': shipment.actual_arrival.isoformat() if shipment.actual_arrival else None,
        'notes': shipment.notes,
        'packages': [
            {
                'id': str(package.id),
                'package_code': package.package_code,
                'description': package.description,
                'supplier_id': str(package.supplier_id) if package.supplier_id else '',
                'supplier_name': package.supplier.name if package.supplier_id else '',
                'is_received': package.is_received,
                'is_stocked': package.is_stocked,
                'is_fragile': package.is_fragile,
                'items': [
                    {
                        'id': str(item.id),
                        'product_id': str(item.product_id),
                        'product_name': item.product.name,
                        'supplier_id': str(item.supplier_id) if item.supplier_id else '',
                        'expected_quantity': item.expected_quantity,
                        'received_quantity': item.received_quantity,
                        'is_verified': item.is_verified,
                        'notes': item.notes,
                        'variant_size': item.variant_size,
                        'variant_color': item.variant_color,
                    }
                    for item in package.items.all()
                ],
            }
            for package in shipment.packages.all()
        ],
    }


def _parse_packages_json(raw_value):
    try:
        packages = json.loads(raw_value or '[]')
    except json.JSONDecodeError as exc:
        raise ValueError('Package data could not be read.') from exc

    if not isinstance(packages, list):
        raise ValueError('Package data must be a list.')
    return packages


def _save_packages(shipment, packages_data, store):
    products = {str(p.id): p for p in Product.objects.filter(store=store, is_active=True)}
    products_by_name = {p.name.lower(): p for p in products.values()}
    suppliers = {str(s.id): s for s in Supplier.objects.filter(store=store)}

    # --- Pass 1: collect all variant data per product and create/update products ---
    # key → {'product': obj|None, 'name': str, 'sizes': set, 'colors': set}
    product_variant_map = {}

    for package_data in packages_data:
        for item_data in package_data.get('items') or []:
            product_id = str(item_data.get('product_id') or '').strip()
            size = (item_data.get('variant_size') or '').strip()
            color = (item_data.get('variant_color') or '').strip()

            if product_id and product_id in products:
                key = product_id
                if key not in product_variant_map:
                    product_variant_map[key] = {'product': products[product_id], 'name': products[product_id].name, 'sizes': set(), 'colors': set()}
            else:
                new_name = (item_data.get('new_product_name') or '').strip()
                if not new_name:
                    continue
                key = '__new__' + new_name.lower()
                if key not in product_variant_map:
                    existing = products_by_name.get(new_name.lower())
                    product_variant_map[key] = {'product': existing, 'name': new_name, 'sizes': set(), 'colors': set()}

            if size:
                product_variant_map[key]['sizes'].add(size)
            if color:
                product_variant_map[key]['colors'].add(color)

    for key, vd in product_variant_map.items():
        product = vd['product']
        sizes = vd['sizes']
        colors = vd['colors']

        if product is None:
            product = Product.objects.create(
                store=store,
                name=vd['name'],
                unit_price=0,
                cost_price=0,
                stock_qty=0,
                is_active=True,
                has_size_variants=bool(sizes),
                size_options=', '.join(sorted(sizes)) if sizes else '',
                has_color_variants=bool(colors),
                color_options=', '.join(sorted(colors)) if colors else '',
            )
            vd['product'] = product
            products[str(product.id)] = product
            products_by_name[product.name.lower()] = product
        elif sizes or colors:
            update_fields = []
            if sizes:
                existing = set(product.size_option_list)
                merged = existing | sizes
                if merged != existing or not product.has_size_variants:
                    product.has_size_variants = True
                    product.size_options = ', '.join(sorted(merged))
                    update_fields += ['has_size_variants', 'size_options']
            if colors:
                existing = set(product.color_option_list)
                merged = existing | colors
                if merged != existing or not product.has_color_variants:
                    product.has_color_variants = True
                    product.color_options = ', '.join(sorted(merged))
                    update_fields += ['has_color_variants', 'color_options']
            if update_fields:
                product.save(update_fields=update_fields)

    # --- Pass 2: create packages and items ---
    seen_codes = set()
    for package_data in packages_data:
        package_code = (package_data.get('package_code') or '').strip()
        if not package_code:
            continue
        if package_code in seen_codes:
            raise ValueError(f'Duplicate package code: {package_code}')
        seen_codes.add(package_code)

        supplier = suppliers.get(str(package_data.get('supplier_id') or '').strip())
        package = ShipmentPackage.objects.create(
            shipment=shipment,
            supplier=supplier,
            package_code=package_code,
            description=(package_data.get('description') or '').strip(),
            is_fragile=bool(package_data.get('is_fragile')),
        )

        items = package_data.get('items') or []
        if not items:
            raise ValueError(f'Package {package_code} needs at least one product item.')

        for item_data in items:
            product_id = str(item_data.get('product_id') or '').strip()
            product = products.get(product_id)
            if not product:
                new_name = (item_data.get('new_product_name') or '').strip()
                if not new_name:
                    raise ValueError(f'Package {package_code} has an item with no product selected.')
                product = products_by_name.get(new_name.lower())
                if not product:
                    raise ValueError(f'Could not resolve product "{new_name}".')

            try:
                expected_quantity = int(item_data.get('expected_quantity') or 0)
            except (TypeError, ValueError):
                expected_quantity = 0
            if expected_quantity <= 0:
                raise ValueError(f'Package {package_code} has an invalid expected quantity for "{product.name}".')

            item_supplier = suppliers.get(str(item_data.get('supplier_id') or '').strip()) or supplier
            ShipmentPackageItem.objects.create(
                package=package,
                supplier=item_supplier,
                product=product,
                expected_quantity=expected_quantity,
                received_quantity=0,
                notes=(item_data.get('notes') or '').strip(),
                variant_size=(item_data.get('variant_size') or '').strip(),
                variant_color=(item_data.get('variant_color') or '').strip(),
            )


@login_required
def shipment_list(request, store_slug):
    store = get_store(store_slug, request.user)
    require_store_permission(request.user, store, 'manage_shipments')
    status = request.GET.get('status', '')
    q = request.GET.get('q', '').strip()

    shipments = _shipment_queryset(store)
    if status:
        shipments = shipments.filter(status=status)
    if q:
        shipments = shipments.filter(
            Q(tracking_number__icontains=q)
            | Q(shipping_company__icontains=q)
            | Q(packages__package_code__icontains=q)
            | Q(packages__supplier__name__icontains=q)
        ).distinct()

    now = timezone.now()
    shipment_expenses = Expense.objects.filter(
        store=store,
        shipment__isnull=False,
        date__year=now.year,
        date__month=now.month,
    ).aggregate(total=Sum('amount'))['total'] or 0

    packages = ShipmentPackage.objects.filter(shipment__store=store).prefetch_related('items')
    pending_packages = packages.filter(is_received=False).count()
    missing_packages = sum(1 for package in packages if package.missing_items_count > 0)

    return render(request, 'shipments/shipment_list.html', {
        'store': store,
        'shipments': shipments,
        'status_filter': status,
        'q': q,
        'status_choices': Shipment.STATUS_CHOICES,
        'in_transit_count': Shipment.objects.filter(store=store, status=Shipment.STATUS_TRANSIT).count(),
        'at_port_count': Shipment.objects.filter(store=store, status=Shipment.STATUS_PORT).count(),
        'pending_packages_count': pending_packages,
        'missing_packages_count': missing_packages,
        'shipment_expenses': shipment_expenses,
    })


@login_required
def shipment_form(request, store_slug, pk=None):
    store = get_store(store_slug, request.user)
    require_store_permission(request.user, store, 'manage_shipments')
    shipment = get_object_or_404(_shipment_queryset(store), pk=pk) if pk else None
    suppliers = Supplier.objects.filter(store=store, is_active=True).order_by('name')
    products = Product.objects.filter(store=store, is_active=True).order_by('name')

    if request.method == 'POST':
        packages_json = request.POST.get('packages_json', '[]')
        try:
            packages_data = _parse_packages_json(packages_json)
        except ValueError as exc:
            packages_data = []
            messages.error(request, str(exc))
        else:
            if not packages_data:
                messages.error(request, 'Add at least one package before saving the shipment.')

        if packages_data:
            try:
                with transaction.atomic():
                    if shipment is None:
                        shipment = Shipment(store=store)

                    shipment.tracking_number = request.POST.get('tracking_number', '').strip()
                    shipment.shipping_company = request.POST.get('shipping_company', '').strip()
                    shipment.method = request.POST.get('method', Shipment.METHOD_SEA)
                    shipment.status = request.POST.get('status', Shipment.STATUS_WAREHOUSE)
                    shipment.origin = request.POST.get('origin', 'China').strip() or 'China'
                    shipment.destination = request.POST.get('destination', 'Ghana').strip() or 'Ghana'
                    shipment.departure_date = request.POST.get('departure_date') or None
                    shipment.estimated_arrival = request.POST.get('estimated_arrival') or None
                    shipment.actual_arrival = request.POST.get('actual_arrival') or None
                    shipment.notes = request.POST.get('notes', '').strip()
                    if request.FILES.get('document'):
                        shipment.document = request.FILES['document']
                    shipment.save()

                    shipment.packages.all().delete()
                    _save_packages(shipment, packages_data, store)
            except ValueError as exc:
                messages.error(request, str(exc))
            else:
                messages.success(request, 'Shipment saved.')
                return redirect('shipments:shipment_detail', store_slug=store.slug, pk=shipment.pk)

    shipment_data = []
    if shipment:
        shipment_data = [
            {
                'package_code': package.package_code,
                'supplier_id': str(package.supplier_id) if package.supplier_id else '',
                'description': package.description,
                'is_fragile': package.is_fragile,
                'items': [
                    {
                        'product_id': str(item.product_id),
                        'supplier_id': str(item.supplier_id) if item.supplier_id else '',
                        'expected_quantity': item.expected_quantity,
                        'notes': item.notes,
                        'variant_size': item.variant_size,
                        'variant_color': item.variant_color,
                    }
                    for item in package.items.all()
                ],
            }
            for package in shipment.packages.all()
        ]

    return render(request, 'shipments/shipment_form.html', {
        'store': store,
        'shipment': shipment,
        'suppliers': suppliers,
        'products': products,
        'packages_json': json.dumps(shipment_data),
        'suppliers_json': json.dumps([
            {'id': str(supplier.id), 'name': supplier.name}
            for supplier in suppliers
        ]),
        'products_json': json.dumps([
            {
                'id': str(product.id),
                'name': product.name,
                'sku': product.sku,
                'sizes': product.size_option_list,
                'colors': product.color_option_list,
            }
            for product in products
        ]),
        'status_choices': Shipment.STATUS_CHOICES,
        'method_choices': Shipment.TRANSPORT_CHOICES,
    })


@login_required
def shipment_detail(request, store_slug, pk):
    store = get_store(store_slug, request.user)
    require_store_permission(request.user, store, 'manage_shipments')
    shipment = get_object_or_404(_shipment_queryset(store), pk=pk)
    expenses = shipment.expenses.order_by('-date', '-created_at')
    shipment_expense_total = expenses.aggregate(total=Sum('amount'))['total'] or 0

    return render(request, 'shipments/shipment_detail.html', {
        'store': store,
        'shipment': shipment,
        'expenses': expenses,
        'shipment_expense_total': shipment_expense_total,
        'status_choices': Shipment.STATUS_CHOICES,
        'shipping_expense_choices': [
            choice for choice in Expense.CATEGORY_CHOICES
            if choice[0] in ('freight', 'customs', 'clearing', 'transport')
        ],
    })


@login_required
@require_POST
def shipment_status(request, store_slug, pk):
    store = get_store(store_slug, request.user)
    require_store_permission(request.user, store, 'manage_shipments')
    shipment = get_object_or_404(Shipment, pk=pk, store=store)
    status = request.POST.get('status', shipment.status)
    note = request.POST.get('note', '').strip()

    if status == Shipment.STATUS_DELIVERED and shipment.packages.filter(is_received=False).exists():
        messages.error(request, 'All packages must be fully received before the shipment can be marked delivered.')
        return redirect('shipments:shipment_detail', store_slug=store.slug, pk=shipment.pk)

    if status in dict(Shipment.STATUS_CHOICES):
        previous_status = shipment.status
        shipment.status = status
        if status == Shipment.STATUS_DELIVERED and not shipment.actual_arrival:
            shipment.actual_arrival = timezone.now().date()
        shipment.save()
        if note:
            if previous_status != shipment.status:
                latest_history = shipment.history.first()
                if latest_history and latest_history.status == shipment.status and not latest_history.note:
                    latest_history.note = note
                    latest_history.save(update_fields=['note'])
            else:
                shipment.history.create(status=shipment.status, note=note)
        messages.success(request, 'Shipment status updated.')

    return redirect('shipments:shipment_detail', store_slug=store.slug, pk=shipment.pk)


@login_required
def package_receive(request, store_slug, pk):
    store = get_store(store_slug, request.user)
    require_store_permission(request.user, store, 'manage_shipments')
    package = get_object_or_404(
        ShipmentPackage.objects.select_related('shipment', 'supplier').prefetch_related(
            Prefetch('items', queryset=ShipmentPackageItem.objects.select_related('product', 'supplier'))
        ),
        pk=pk,
        shipment__store=store,
    )

    if request.method == 'POST':
        action = request.POST.get('action', 'save')
        with transaction.atomic():
            for item in package.items.all():
                raw_qty = request.POST.get(f'received_{item.pk}', item.received_quantity)
                try:
                    item.received_quantity = max(int(raw_qty), 0)
                except (TypeError, ValueError):
                    item.received_quantity = 0
                item.notes = request.POST.get(f'notes_{item.pk}', '').strip()
                item.shortage_reason = request.POST.get(f'shortage_reason_{item.pk}', '').strip()
                raw_cost = request.POST.get(f'cost_price_{item.pk}', '').strip()
                raw_unit = request.POST.get(f'unit_price_{item.pk}', '').strip()
                try:
                    item.cost_price = float(raw_cost) if raw_cost else item.cost_price
                except ValueError:
                    pass
                try:
                    item.unit_price = float(raw_unit) if raw_unit else item.unit_price
                except ValueError:
                    pass
                item.save()

            package.refresh_from_db()
            if action == 'complete':
                package = ShipmentPackage.objects.prefetch_related('items').get(pk=package.pk)
                package.complete_receiving()
                missing = package.missing_quantity_total
                if missing:
                    messages.success(request, f'Package confirmed. {missing} missing item(s) recorded. Received stock pushed to inventory.')
                else:
                    messages.success(request, 'Package fully received and inventory updated.')
                return redirect('shipments:shipment_detail', store_slug=store.slug, pk=package.shipment_id)
            else:
                messages.success(request, 'Receiving progress saved.')

    package = ShipmentPackage.objects.select_related('shipment', 'supplier').prefetch_related(
        Prefetch('items', queryset=ShipmentPackageItem.objects.select_related('product', 'supplier'))
    ).get(pk=package.pk)

    return render(request, 'shipments/package_receive.html', {
        'store': store,
        'package': package,
    })


def _json_error(message, status=400):
    return JsonResponse({'error': message}, status=status)


@login_required
@require_http_methods(['GET', 'POST'])
def api_shipments(request, store_slug):
    store = get_store(store_slug, request.user)
    require_store_permission(request.user, store, 'manage_shipments')

    if request.method == 'GET':
        status = request.GET.get('status', '').strip()
        shipments = _shipment_queryset(store)
        if status:
            shipments = shipments.filter(status=status)
        return JsonResponse([_serialize_shipment(shipment) for shipment in shipments[:50]], safe=False)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return _json_error('Invalid JSON.')

    tracking_number = (data.get('tracking_number') or '').strip()
    shipping_company = (data.get('shipping_company') or '').strip()
    if not tracking_number or not shipping_company:
        return _json_error('tracking_number and shipping_company are required.')

    with transaction.atomic():
        shipment = Shipment.objects.create(
            store=store,
            tracking_number=tracking_number,
            shipping_company=shipping_company,
            method=data.get('method') or Shipment.METHOD_SEA,
            status=data.get('status') or Shipment.STATUS_WAREHOUSE,
            origin=(data.get('origin') or 'China').strip() or 'China',
            destination=(data.get('destination') or 'Ghana').strip() or 'Ghana',
            departure_date=data.get('departure_date') or None,
            estimated_arrival=data.get('estimated_arrival') or None,
            actual_arrival=data.get('actual_arrival') or None,
            notes=(data.get('notes') or '').strip(),
        )
        try:
            _save_packages(shipment, data.get('packages') or [], store)
        except ValueError as exc:
            transaction.set_rollback(True)
            return _json_error(str(exc))

    return JsonResponse(_serialize_shipment(_shipment_queryset(store).get(pk=shipment.pk)), status=201)


@login_required
@require_http_methods(['GET', 'PATCH'])
def api_shipment_detail(request, store_slug, pk):
    store = get_store(store_slug, request.user)
    require_store_permission(request.user, store, 'manage_shipments')
    shipment = get_object_or_404(_shipment_queryset(store), pk=pk)

    if request.method == 'GET':
        return JsonResponse(_serialize_shipment(shipment))

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return _json_error('Invalid JSON.')

    for field in ('tracking_number', 'shipping_company', 'origin', 'destination', 'notes'):
        if field in data:
            setattr(shipment, field, data[field] or '')
    for field in ('departure_date', 'estimated_arrival', 'actual_arrival'):
        if field in data:
            setattr(shipment, field, data[field] or None)
    if 'method' in data and data['method'] in dict(Shipment.TRANSPORT_CHOICES):
        shipment.method = data['method']
    if 'status' in data and data['status'] in dict(Shipment.STATUS_CHOICES):
        if data['status'] == Shipment.STATUS_DELIVERED and shipment.packages.filter(is_received=False).exists():
            return _json_error('All packages must be received before marking shipment delivered.')
        shipment.status = data['status']
    shipment.save()

    return JsonResponse(_serialize_shipment(_shipment_queryset(store).get(pk=shipment.pk)))


@login_required
@require_http_methods(['GET', 'POST'])
def api_packages(request, store_slug):
    store = get_store(store_slug, request.user)
    require_store_permission(request.user, store, 'manage_shipments')

    if request.method == 'GET':
        packages = ShipmentPackage.objects.filter(shipment__store=store).select_related('shipment', 'supplier').prefetch_related('items__product')
        status = request.GET.get('status', '').strip()
        supplier = request.GET.get('supplier', '').strip()
        if status:
            packages = packages.filter(shipment__status=status)
        if supplier:
            packages = packages.filter(supplier_id=supplier)
        return JsonResponse([
            {
                'id': str(package.id),
                'shipment_id': str(package.shipment_id),
                'shipment_tracking_number': package.shipment.tracking_number,
                'package_code': package.package_code,
                'supplier_id': str(package.supplier_id) if package.supplier_id else '',
                'is_received': package.is_received,
                'is_stocked': package.is_stocked,
                'items': [
                    {
                        'product_name': item.product.name,
                        'expected_quantity': item.expected_quantity,
                        'received_quantity': item.received_quantity,
                    }
                    for item in package.items.all()
                ],
            }
            for package in packages[:100]
        ], safe=False)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return _json_error('Invalid JSON.')

    shipment = Shipment.objects.filter(store=store, pk=data.get('shipment_id')).first()
    if not shipment:
        return _json_error('Valid shipment_id is required.')

    try:
        _save_packages(shipment, [data], store)
    except ValueError as exc:
        return _json_error(str(exc))

    package = ShipmentPackage.objects.filter(shipment=shipment).order_by('-created_at').first()
    return JsonResponse({'id': str(package.id), 'package_code': package.package_code}, status=201)
