from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST
from django.utils import timezone

from core.views import get_store
from core.models import StoreStaff
from inventory.models import Product, Category
from .models import ProcurementPlan, ProcurementItem


@login_required
def plan_list(request, store_slug):
    store = get_store(store_slug, request.user)
    status_filter = request.GET.get('status', '')
    plans = ProcurementPlan.objects.filter(store=store)
    if status_filter:
        plans = plans.filter(status=status_filter)
    return render(request, 'procurement/plan_list.html', {
        'store': store,
        'plans': plans,
        'status_filter': status_filter,
        'status_choices': ProcurementPlan.STATUS_CHOICES,
    })


@login_required
def plan_create(request, store_slug):
    store = get_store(store_slug, request.user)
    categories = Category.objects.filter(store=store)
    staff = StoreStaff.objects.filter(store=store, is_active=True)

    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        planned_date = request.POST.get('planned_date')
        notes = request.POST.get('notes', '')
        staff_id = request.POST.get('created_by', '')

        if not title or not planned_date:
            return render(request, 'procurement/plan_form.html', {
                'store': store, 'categories': categories, 'staff': staff,
                'error': 'Title and planned date are required.',
            })

        plan = ProcurementPlan(store=store, title=title, planned_date=planned_date, notes=notes)
        if staff_id:
            try:
                plan.created_by = StoreStaff.objects.get(pk=staff_id, store=store)
            except StoreStaff.DoesNotExist:
                pass
        plan.save()

        _save_items(request, plan, store)
        return redirect('procurement:plan_detail', store_slug=store.slug, pk=plan.pk)

    return render(request, 'procurement/plan_form.html', {
        'store': store, 'categories': categories, 'staff': staff,
    })


@login_required
def plan_edit(request, store_slug, pk):
    store = get_store(store_slug, request.user)
    plan = get_object_or_404(ProcurementPlan, pk=pk, store=store)
    if plan.status != 'draft':
        return redirect('procurement:plan_detail', store_slug=store.slug, pk=pk)

    categories = Category.objects.filter(store=store)
    staff = StoreStaff.objects.filter(store=store, is_active=True)

    if request.method == 'POST':
        plan.title = request.POST.get('title', plan.title).strip()
        plan.planned_date = request.POST.get('planned_date', plan.planned_date)
        plan.notes = request.POST.get('notes', '')
        staff_id = request.POST.get('created_by', '')
        if staff_id:
            try:
                plan.created_by = StoreStaff.objects.get(pk=staff_id, store=store)
            except StoreStaff.DoesNotExist:
                pass
        plan.save()
        plan.items.all().delete()
        _save_items(request, plan, store)
        return redirect('procurement:plan_detail', store_slug=store.slug, pk=pk)

    return render(request, 'procurement/plan_form.html', {
        'store': store, 'plan': plan,
        'categories': categories, 'staff': staff,
    })


def _save_items(request, plan, store):
    names = request.POST.getlist('item_name')
    product_ids = request.POST.getlist('item_product_id')
    cat_ids = request.POST.getlist('item_category_id')
    qtys = request.POST.getlist('item_qty')
    costs = request.POST.getlist('item_cost')
    suppliers = request.POST.getlist('item_supplier')
    locations = request.POST.getlist('item_location')

    for i, name in enumerate(names):
        name = name.strip()
        if not name:
            continue
        qty = max(1, int(qtys[i]) if qtys[i].isdigit() else 1)
        try:
            cost = float(costs[i]) if costs[i].strip() else 0
        except (ValueError, IndexError):
            cost = 0

        product = None
        pid = product_ids[i].strip() if i < len(product_ids) else ''
        if pid:
            try:
                product = Product.objects.get(pk=pid, store=store)
            except Product.DoesNotExist:
                pass

        category = None
        cid = cat_ids[i].strip() if i < len(cat_ids) else ''
        if cid:
            try:
                category = Category.objects.get(pk=cid, store=store)
            except Category.DoesNotExist:
                pass
        elif product and product.category:
            category = product.category

        current_stock = product.stock_qty if product else 0
        est_cost = cost or (float(product.cost_price) if product else 0)

        ProcurementItem.objects.create(
            plan=plan,
            product=product,
            new_product_name='' if product else name,
            category=category,
            planned_qty=qty,
            estimated_unit_cost=est_cost,
            supplier_name=suppliers[i].strip() if i < len(suppliers) else '',
            supplier_location=locations[i].strip() if i < len(locations) else '',
            current_stock=current_stock,
        )


@login_required
def plan_detail(request, store_slug, pk):
    store = get_store(store_slug, request.user)
    plan = get_object_or_404(ProcurementPlan, pk=pk, store=store)
    items = plan.items.select_related('product', 'category').all()
    fulfil_result = request.session.pop('fulfil_result', None)
    return render(request, 'procurement/plan_detail.html', {
        'store': store, 'plan': plan, 'items': items,
        'fulfil_result': fulfil_result,
    })


@login_required
def plan_fulfil(request, store_slug, pk):
    store = get_store(store_slug, request.user)
    plan = get_object_or_404(ProcurementPlan, pk=pk, store=store)
    if plan.status != 'in_progress':
        return redirect('procurement:plan_detail', store_slug=store.slug, pk=pk)

    items = plan.items.select_related('product', 'category').all()

    if request.method == 'POST':
        errors = []
        for item in items:
            sid = str(item.pk)
            is_fulfilled = request.POST.get(f'fulfilled_{sid}') == 'on'
            item.is_fulfilled = is_fulfilled

            if is_fulfilled:
                try:
                    item.actual_qty = int(request.POST.get(f'actual_qty_{sid}', item.planned_qty))
                except (ValueError, TypeError):
                    item.actual_qty = item.planned_qty
                try:
                    item.actual_unit_cost = float(request.POST.get(f'actual_cost_{sid}', 0) or 0)
                except (ValueError, TypeError):
                    item.actual_unit_cost = None

                item.is_paid = request.POST.get(f'is_paid_{sid}') == 'on'
                item.available_for_preorder = request.POST.get(f'preorder_{sid}') == 'on'

                if not item.product:
                    sp_raw = request.POST.get(f'selling_price_{sid}', '').strip()
                    if not sp_raw:
                        errors.append(f"Selling price required for new product: {item.new_product_name}")
                        continue
                    item.selling_price = float(sp_raw)

            item.save()

        if errors:
            return render(request, 'procurement/plan_fulfil.html', {
                'store': store, 'plan': plan, 'items': items, 'errors': errors,
            })

        from .services import fulfil_plan
        result = fulfil_plan(plan)
        request.session['fulfil_result'] = result
        return redirect('procurement:plan_detail', store_slug=store.slug, pk=pk)

    return render(request, 'procurement/plan_fulfil.html', {
        'store': store, 'plan': plan, 'items': items,
    })


@login_required
@require_POST
def plan_status(request, store_slug, pk):
    store = get_store(store_slug, request.user)
    plan = get_object_or_404(ProcurementPlan, pk=pk, store=store)
    action = request.POST.get('action')

    transitions = {
        'approve':   ('draft',       'approved'),
        'start':     ('approved',    'in_progress'),
        'cancel':    ('draft',       'cancelled'),
        'cancel_ap': ('approved',    'cancelled'),
    }
    if action in transitions:
        from_status, to_status = transitions[action]
        if plan.status == from_status:
            plan.status = to_status
            plan.save(update_fields=['status'])

    return redirect('procurement:plan_detail', store_slug=store.slug, pk=pk)
