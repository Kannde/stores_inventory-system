
from django.contrib import messages
from django.views.decorators.cache import never_cache
from django.contrib.admin.models import LogEntry
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, F, Q, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils import timezone

from .access import (
    can_manage_staff,
    get_store_capabilities,
    get_post_login_redirect,
    get_store_for_user,
    get_store_role_label,
    get_user_store,
    is_store_owner,
)
from .forms import AdminStoreForm, LoginForm, OwnerForm, StaffForm, StoreSettingsForm
from .models import Store, StoreSettings, StoreStaff

User = get_user_model()


def get_store(store_slug, user=None):
    return get_store_for_user(store_slug, user=user)


def build_store_permissions(user, store):
    permissions = get_store_capabilities(user, store)
    permissions.update({
        'can_edit_store': is_store_owner(user, store),
        'can_manage_staff': can_manage_staff(user, store),
        'current_role_label': get_store_role_label(user, store),
    })
    return permissions


def home(request):
    if request.user.is_authenticated and request.user.is_superuser:
        return redirect('core:admin_landing')

    if request.user.is_authenticated:
        store = get_user_store(request.user)
        if store:
            return redirect('core:store_dashboard', store_slug=store.slug)
        messages.error(request, 'Your account is not linked to a store yet.')
        logout(request)

    return redirect('core:login')


def login_view(request):
    if request.user.is_authenticated and request.user.is_superuser:
        return redirect('core:admin_landing')

    if request.user.is_authenticated:
        store = get_user_store(request.user)
        if store:
            return redirect('core:store_dashboard', store_slug=store.slug)
        messages.error(request, 'Your account is not linked to a store yet.')
        logout(request)

    form = LoginForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = authenticate(
            request,
            username=form.cleaned_data['username'],
            password=form.cleaned_data['password'],
        )
        if user is None:
            form.add_error(None, 'Invalid username or password.')
        elif not user.is_superuser and not get_user_store(user):
            form.add_error(None, 'This account is not linked to a store yet.')
        else:
            login(request, user)
            return redirect(get_post_login_redirect(user))

    return render(request, 'core/login.html', {'form': form})


@login_required
def logout_view(request):
    logout(request)
    return redirect('core:login')


@login_required
def admin_landing(request):
    if not request.user.is_superuser:
        raise PermissionDenied

    stores = Store.objects.select_related('owner').annotate(
        staff_count=Count('staff', filter=Q(staff__is_active=True))
    ).order_by('name')

    context = {
        'stores': stores,
        'total_stores': stores.count(),
        'active_stores': stores.filter(is_active=True).count(),
        'inactive_stores': stores.filter(is_active=False).count(),
        'owner_count': User.objects.filter(is_superuser=False, owned_store__isnull=False).count(),
        'recent_logs': LogEntry.objects.select_related('user', 'content_type').order_by('-action_time')[:8],
    }
    return render(request, 'core/admin_landing.html', context)


@login_required
def admin_store_create(request):
    if not request.user.is_superuser:
        raise PermissionDenied

    form = AdminStoreForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Store created.')
        return redirect('core:admin_landing')

    return render(request, 'core/admin_store_form.html', {'form': form, 'title': 'Create Store'})


@login_required
def admin_store_edit(request, pk):
    if not request.user.is_superuser:
        raise PermissionDenied

    store = get_object_or_404(Store, pk=pk)
    form = AdminStoreForm(request.POST or None, request.FILES or None, instance=store)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Store updated.')
        return redirect('core:admin_landing')

    return render(request, 'core/admin_store_form.html', {'form': form, 'store': store, 'title': 'Edit Store'})


@login_required
def admin_store_toggle(request, pk):
    if not request.user.is_superuser:
        raise PermissionDenied

    store = get_object_or_404(Store, pk=pk)
    store.is_active = not store.is_active
    store.save(update_fields=['is_active'])
    status = 'activated' if store.is_active else 'deactivated'
    messages.success(request, f'"{store.name}" {status}.')
    return redirect('core:admin_landing')


@login_required
def admin_owners(request):
    if not request.user.is_superuser:
        raise PermissionDenied

    owners = User.objects.filter(is_superuser=False).select_related('owned_store').order_by('username')
    return render(request, 'core/admin_owner_list.html', {'owners': owners})


@login_required
def admin_owner_create(request):
    if not request.user.is_superuser:
        raise PermissionDenied

    form = OwnerForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Owner account created.')
        return redirect('core:admin_owners')

    return render(request, 'core/admin_owner_form.html', {'form': form, 'title': 'Create Owner'})


@login_required
def admin_owner_edit(request, pk):
    if not request.user.is_superuser:
        raise PermissionDenied

    owner = get_object_or_404(User, pk=pk)
    form = OwnerForm(request.POST or None, instance=owner)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Owner updated.')
        return redirect('core:admin_owners')

    return render(request, 'core/admin_owner_form.html', {'form': form, 'owner': owner, 'title': 'Edit Owner'})


@login_required
def admin_logs(request):
    if not request.user.is_superuser:
        raise PermissionDenied

    logs = LogEntry.objects.select_related('user', 'content_type').order_by('-action_time')[:100]
    return render(request, 'core/admin_logs.html', {'logs': logs})


@login_required
def store_dashboard(request, store_slug):
    store = get_store(store_slug, request.user)
    today = timezone.now().date()

    from django.db.models import ExpressionWrapper, DecimalField
    from inventory.models import Product, Category, Supplier
    from preorders.models import PreOrder, PreOrderItem
    from shipments.models import Shipment, ShipmentPackage
    from sales.models import Sale, CreditAccount, SaleItem
    from expenses.models import Expense
    from core.date_filter import resolve_period, parse_entity_filters

    pf = resolve_period(request, today, default='this_week')
    ef = parse_entity_filters(request)
    start_date, end_date = pf['start_date'], pf['end_date']
    active_staff_id = ef['active_staff_id']
    active_category_id = ef['active_category_id']
    active_product_id = ef['active_product_id']

    # Period revenue/count — item-level when category/product filter active
    if active_category_id or active_product_id:
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
        fi = SaleItem.objects.filter(**item_q)
        period_revenue = fi.aggregate(t=Sum('line_total'))['t'] or 0
        period_count = fi.values('sale').distinct().count()
    else:
        sale_q = {
            'store': store,
            'created_at__date__gte': start_date,
            'created_at__date__lte': end_date,
            'status': 'completed',
        }
        if active_staff_id:
            sale_q['staff__pk'] = active_staff_id
        ps = Sale.objects.filter(**sale_q)
        period_revenue = ps.aggregate(t=Sum('total_amount'))['t'] or 0
        period_count = ps.count()

    avg_sale = float(period_revenue) / max(period_count, 1)

    # Credit overview (global, not period-filtered)
    total_receivables = CreditAccount.objects.filter(
        store=store, is_settled=False,
    ).aggregate(
        total=Sum(ExpressionWrapper(F('total_amount') - F('amount_paid'), output_field=DecimalField()))
    )['total'] or 0

    supplier_debt = Supplier.objects.filter(
        store=store, is_active=True, outstanding_balance__gt=0,
    ).aggregate(total=Sum('outstanding_balance'))['total'] or 0

    current_month = today.month
    current_year = today.year
    shipment_expenses = Expense.objects.filter(
        store=store,
        shipment__isnull=False,
        date__year=current_year,
        date__month=current_month,
    ).aggregate(total=Sum('amount'))['total'] or 0

    _po_expr = ExpressionWrapper(F('quantity') * F('unit_price'), output_field=DecimalField())
    preorder_obligation = PreOrderItem.objects.filter(
        preorder__store=store,
        preorder__status__in=['pending', 'confirmed', 'ready'],
        unit_price__gt=0,
    ).aggregate(total=Sum(_po_expr))['total'] or 0

    net_credit = total_receivables - supplier_debt

    # Filter dropdown data
    filter_staff = StoreStaff.objects.filter(store=store, is_active=True).order_by('name')
    filter_categories = Category.objects.filter(store=store).order_by('name')
    filter_products = Product.objects.filter(store=store, is_active=True).order_by('name')

    context = {
        'store': store,
        'period_revenue': period_revenue,
        'period_count': period_count,
        'avg_sale': avg_sale,
        'total_products': Product.objects.filter(store=store, is_active=True).count(),
        'low_stock': Product.objects.filter(
            store=store, is_active=True, stock_qty__lte=F('reorder_level'),
        ).count(),
        'out_of_stock': Product.objects.filter(store=store, is_active=True, stock_qty__lte=0).count(),
        'pending_preorders': PreOrder.objects.filter(store=store, status='pending').count(),
        'recent_sales': Sale.objects.filter(store=store).select_related('staff')[:5],
        'staff_count': StoreStaff.objects.filter(store=store, is_active=True).count(),
        'total_receivables': total_receivables,
        'supplier_debt': supplier_debt,
        'preorder_obligation': preorder_obligation,
        'net_credit': net_credit,
        'shipments_in_transit': Shipment.objects.filter(store=store, status='TRANSIT').count(),
        'shipments_at_port': Shipment.objects.filter(store=store, status='PORT').count(),
        'packages_pending_receiving': ShipmentPackage.objects.filter(shipment__store=store, is_received=False).count(),
        'packages_missing_items': ShipmentPackage.objects.filter(
            shipment__store=store,
            items__received_quantity__lt=F('items__expected_quantity'),
        ).distinct().count(),
        'shipment_expenses_monthly': shipment_expenses,
        'filter_staff': filter_staff,
        'filter_categories': filter_categories,
        'filter_products': filter_products,
        **pf,
        **ef,
        **build_store_permissions(request.user, store),
    }
    return render(request, 'core/dashboard.html', context)


@login_required
def staff_list(request, store_slug):
    store = get_store(store_slug, request.user)
    if not can_manage_staff(request.user, store):
        raise PermissionDenied

    staff = StoreStaff.objects.filter(store=store)
    return render(request, 'core/staff_list.html', {
        'store': store,
        'staff': staff,
        **build_store_permissions(request.user, store),
    })


@login_required
def staff_add(request, store_slug):
    store = get_store(store_slug, request.user)
    if not can_manage_staff(request.user, store):
        raise PermissionDenied

    form = StaffForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save(store=store)
        messages.success(request, 'Staff member saved.')
        return redirect('core:staff_list', store_slug=store.slug)

    return render(request, 'core/staff_form.html', {
        'store': store,
        'form': form,
        'staff_member': None,
        **build_store_permissions(request.user, store),
    })


@login_required
def staff_edit(request, store_slug, pk):
    store = get_store(store_slug, request.user)
    if not can_manage_staff(request.user, store):
        raise PermissionDenied

    member = get_object_or_404(StoreStaff, pk=pk, store=store)
    form = StaffForm(request.POST or None, instance=member)
    if request.method == 'POST' and form.is_valid():
        form.save(store=store)
        messages.success(request, 'Staff member updated.')
        return redirect('core:staff_list', store_slug=store.slug)

    return render(request, 'core/staff_form.html', {
        'store': store,
        'form': form,
        'staff_member': member,
        **build_store_permissions(request.user, store),
    })


@login_required
def staff_toggle(request, store_slug, pk):
    store = get_store(store_slug, request.user)
    if not can_manage_staff(request.user, store):
        raise PermissionDenied

    member = get_object_or_404(StoreStaff, pk=pk, store=store)
    member.is_active = not member.is_active
    member.save(update_fields=['is_active'])
    if member.user_id:
        member.user.is_active = member.is_active
        member.user.save(update_fields=['is_active'])

    messages.success(request, 'Staff status updated.')
    return redirect('core:staff_list', store_slug=store.slug)


@login_required
def store_settings(request, store_slug):
    store = get_store(store_slug, request.user)
    if not is_store_owner(request.user, store):
        raise PermissionDenied

    settings_obj, _ = StoreSettings.objects.get_or_create(store=store)

    form = StoreSettingsForm(request.POST or None, request.FILES or None, instance=store)
    if request.method == 'POST' and form.is_valid():
        form.save()
        settings_obj.allow_partial_payment = request.POST.get('allow_partial_payment') == 'on'
        settings_obj.allow_credit = request.POST.get('allow_credit') == 'on'
        settings_obj.min_deposit_percent = request.POST.get('min_deposit_percent') or 30
        settings_obj.preorder_enabled = request.POST.get('preorder_enabled') == 'on'
        settings_obj.preorder_payment_policy = request.POST.get('preorder_payment_policy', 'on_delivery')
        settings_obj.preorder_deposit_percent = request.POST.get('preorder_deposit_percent') or 30
        settings_obj.preorder_expected_days = request.POST.get('preorder_expected_days') or 7
        settings_obj.preorder_welcome_message = request.POST.get('preorder_welcome_message', '')
        settings_obj.preorder_whatsapp_number = request.POST.get('preorder_whatsapp_number', '')
        settings_obj.preorder_all_products = request.POST.get('preorder_all_products') == 'on'
        settings_obj.manager_can_manage_shipments = request.POST.get('manager_can_manage_shipments') == 'on'
        settings_obj.save()
        messages.success(request, 'Store settings updated.')
        return redirect('core:store_settings', store_slug=store.slug)

    return render(request, 'core/store_form.html', {
        'store': store,
        'form': form,
        'store_settings': settings_obj,
        **build_store_permissions(request.user, store),
    })


@never_cache
def service_worker(request):
    import hashlib, time
    version = hashlib.md5(str(int(time.time() / 3600)).encode()).hexdigest()[:8]
    content = render_to_string('sw.js', {'cache_version': version})
    return HttpResponse(content, content_type='application/javascript; charset=utf-8',
                        headers={'Service-Worker-Allowed': '/'})


def offline_view(request):
    return render(request, 'offline.html')
