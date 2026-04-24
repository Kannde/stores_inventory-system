from django.core.exceptions import ObjectDoesNotExist, PermissionDenied
from django.shortcuts import get_object_or_404
from django.urls import reverse

from .models import Store, StoreSettings


ROLE_PERMISSIONS = {
    'manager': {
        'view_dashboard',
        'view_financial_dashboard',
        'sell',
        'view_inventory',
        'manage_inventory',
        'view_stock',
        'manage_suppliers',
        'view_expenses',
        'view_reports',
        'manage_procurement',
        'manage_staff',
        'manage_preorders',
        'manage_credit',
    },
    'stock': {
        'view_dashboard',
        'view_inventory',
        'manage_inventory',
        'view_stock',
        'manage_suppliers',
        'manage_procurement',
    },
    'sales': {
        'view_dashboard',
        'sell',
        'view_inventory',
        'view_stock',
    },
}


def get_owned_store(user):
    if not user.is_authenticated or user.is_superuser:
        return None

    try:
        return user.owned_store
    except ObjectDoesNotExist:
        return None


def get_staff_profile(user):
    if not user.is_authenticated or user.is_superuser:
        return None

    try:
        return user.store_staff_profile
    except ObjectDoesNotExist:
        return None


def get_store_for_user(store_slug, user=None):
    store = get_object_or_404(Store, slug=store_slug, is_active=True)
    if user is None:
        return store
    if not user.is_authenticated:
        raise PermissionDenied
    if user.is_superuser:
        return store

    owner_store = get_owned_store(user)
    if owner_store and owner_store.pk == store.pk:
        return store

    staff_profile = get_staff_profile(user)
    if staff_profile and staff_profile.is_active and staff_profile.store_id == store.pk:
        return store

    raise PermissionDenied


def get_user_store(user):
    if not user.is_authenticated or user.is_superuser:
        return None

    owner_store = get_owned_store(user)
    if owner_store and owner_store.is_active:
        return owner_store

    staff_profile = get_staff_profile(user)
    if staff_profile and staff_profile.is_active and staff_profile.store.is_active:
        return staff_profile.store

    return None


def is_store_owner(user, store):
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True

    owner_store = get_owned_store(user)
    return bool(owner_store and owner_store.pk == store.pk)


def get_store_settings(store):
    try:
        return store.settings
    except ObjectDoesNotExist:
        settings_obj, _ = StoreSettings.objects.get_or_create(store=store)
        return settings_obj


def get_store_capabilities(user, store):
    base = {
        'can_edit_store': False,
        'can_manage_staff': False,
        'can_view_dashboard': False,
        'can_view_financial_dashboard': False,
        'can_sell': False,
        'can_view_inventory': False,
        'can_manage_inventory': False,
        'can_view_stock': False,
        'can_manage_suppliers': False,
        'can_view_expenses': False,
        'can_view_reports': False,
        'can_manage_procurement': False,
        'can_manage_shipments': False,
        'can_manage_preorders': False,
        'can_manage_credit': False,
    }

    if not user.is_authenticated:
        return base

    if user.is_superuser or is_store_owner(user, store):
        for key in base:
            base[key] = True
        return base

    staff_profile = get_staff_profile(user)
    if not (staff_profile and staff_profile.is_active and staff_profile.store_id == store.pk):
        return base

    for permission in ROLE_PERMISSIONS.get(staff_profile.role, set()):
        key = f'can_{permission}'
        if key in base:
            base[key] = True

    if staff_profile.role == 'manager' and get_store_settings(store).manager_can_manage_shipments:
        base['can_manage_shipments'] = True

    return base


def has_store_permission(user, store, permission):
    return get_store_capabilities(user, store).get(f'can_{permission}', False)


def require_store_permission(user, store, permission):
    if not has_store_permission(user, store, permission):
        raise PermissionDenied


def can_manage_staff(user, store):
    return has_store_permission(user, store, 'manage_staff')


def get_store_role_label(user, store):
    if not user.is_authenticated:
        return ''
    if user.is_superuser:
        return 'Superuser'
    if is_store_owner(user, store):
        return 'Store Owner'

    staff_profile = get_staff_profile(user)
    if staff_profile and staff_profile.store_id == store.pk:
        return staff_profile.get_role_display()

    return ''


def get_post_login_redirect(user):
    if user.is_superuser:
        return reverse('core:admin_landing')

    store = get_user_store(user)
    if store:
        return reverse('core:store_dashboard', kwargs={'store_slug': store.slug})

    return reverse('core:login')
