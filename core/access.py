from django.core.exceptions import ObjectDoesNotExist, PermissionDenied
from django.shortcuts import get_object_or_404
from django.urls import reverse

from .models import Store


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


def can_manage_staff(user, store):
    if not user.is_authenticated:
        return False
    if is_store_owner(user, store):
        return True

    staff_profile = get_staff_profile(user)
    return bool(
        staff_profile
        and staff_profile.is_active
        and staff_profile.store_id == store.pk
        and staff_profile.role == 'manager'
    )


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
