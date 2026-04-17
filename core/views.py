from datetime import timedelta

from django.contrib import messages
from django.contrib.admin.models import LogEntry
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, F, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .access import (
    can_manage_staff,
    get_post_login_redirect,
    get_store_for_user,
    get_store_role_label,
    get_user_store,
    is_store_owner,
)
from .forms import AdminStoreForm, LoginForm, OwnerForm, StaffForm, StoreSettingsForm
from .models import Store, StoreStaff

User = get_user_model()


def get_store(store_slug, user=None):
    return get_store_for_user(store_slug, user=user)


def build_store_permissions(user, store):
    return {
        'can_edit_store': is_store_owner(user, store),
        'can_manage_staff': can_manage_staff(user, store),
        'current_role_label': get_store_role_label(user, store),
    }


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
    week_ago = today - timedelta(days=7)

    from inventory.models import Product
    from preorders.models import PreOrder
    from sales.models import Sale

    today_sales = Sale.objects.filter(store=store, created_at__date=today)
    week_sales = Sale.objects.filter(store=store, created_at__date__gte=week_ago)

    context = {
        'store': store,
        'today_revenue': today_sales.aggregate(t=Sum('total_amount'))['t'] or 0,
        'today_count': today_sales.count(),
        'week_revenue': week_sales.aggregate(t=Sum('total_amount'))['t'] or 0,
        'week_count': week_sales.count(),
        'total_products': Product.objects.filter(store=store, is_active=True).count(),
        'low_stock': Product.objects.filter(
            store=store,
            is_active=True,
            stock_qty__lte=F('reorder_level'),
        ).count(),
        'out_of_stock': Product.objects.filter(store=store, is_active=True, stock_qty__lte=0).count(),
        'pending_preorders': PreOrder.objects.filter(store=store, status='pending').count(),
        'recent_sales': Sale.objects.filter(store=store).select_related('staff')[:5],
        'staff_count': StoreStaff.objects.filter(store=store, is_active=True).count(),
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

    form = StoreSettingsForm(request.POST or None, request.FILES or None, instance=store)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Store details updated.')
        return redirect('core:store_settings', store_slug=store.slug)

    return render(request, 'core/store_form.html', {
        'store': store,
        'form': form,
        **build_store_permissions(request.user, store),
    })
