from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from core.views import get_store
from .models import PreOrder, PreOrderItem


def preorder_form(request, store_slug):
    store = get_store(store_slug)
    if request.method == 'POST':
        po = PreOrder.objects.create(
            store=store,
            customer_name=request.POST['customer_name'],
            customer_phone=request.POST['customer_phone'],
            customer_email=request.POST.get('customer_email', ''),
            notes=request.POST.get('notes', ''),
            desired_date=request.POST.get('desired_date') or None,
        )
        descriptions = request.POST.getlist('item_description')
        quantities = request.POST.getlist('item_qty')
        units = request.POST.getlist('item_unit')
        for desc, qty, unit in zip(descriptions, quantities, units):
            if desc.strip():
                PreOrderItem.objects.create(
                    preorder=po,
                    item_description=desc.strip(),
                    quantity=int(qty) if qty else 1,
                    unit_label=unit or 'unit',
                )
        return redirect('preorders:preorder_success', store_slug=store.slug)
    return render(request, 'preorders/preorder_form.html', {'store': store})


def preorder_success(request, store_slug):
    store = get_store(store_slug)
    return render(request, 'preorders/preorder_success.html', {'store': store})


def preorder_list(request, store_slug):
    store = get_store(store_slug)
    status = request.GET.get('status', 'pending')
    preorders = PreOrder.objects.filter(store=store)
    if status != 'all':
        preorders = preorders.filter(status=status)
    return render(request, 'preorders/preorder_list.html', {
        'store': store, 'preorders': preorders, 'current_status': status,
    })


def preorder_detail(request, store_slug, pk):
    store = get_store(store_slug)
    po = get_object_or_404(PreOrder, pk=pk, store=store)
    return render(request, 'preorders/preorder_detail.html', {'store': store, 'preorder': po})


def preorder_status(request, store_slug, pk):
    store = get_store(store_slug)
    po = get_object_or_404(PreOrder, pk=pk, store=store)
    if request.method == 'POST':
        new_status = request.POST.get('status')
        if new_status in dict(PreOrder.STATUS_CHOICES):
            po.status = new_status
            po.staff_notes = request.POST.get('staff_notes', po.staff_notes)
            po.save(update_fields=['status', 'staff_notes'])
    return redirect('preorders:preorder_detail', store_slug=store.slug, pk=po.pk)
