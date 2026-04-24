from django.core.exceptions import PermissionDenied

from .access import get_store_capabilities, get_store_for_user


def store_permissions(request):
    match = getattr(request, 'resolver_match', None)
    if not match:
        return {}

    store_slug = match.kwargs.get('store_slug')
    if not store_slug or not request.user.is_authenticated:
        return {}

    try:
        store = get_store_for_user(store_slug, request.user)
    except PermissionDenied:
        return {}

    return get_store_capabilities(request.user, store)
