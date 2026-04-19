def _extract_prefix(name):
    """Derive a 3-letter prefix from a name by taking the first 3 consonants."""
    consonants = [c for c in name.upper() if c.isalpha() and c not in 'AEIOU']
    vowels = [c for c in name.upper() if c.isalpha() and c in 'AEIOU']
    chars = consonants[:3]
    if len(chars) < 3:
        chars += vowels[:3 - len(chars)]
    while len(chars) < 3:
        chars.append('X')
    return ''.join(chars[:3])


def generate_sku(store, category=None, product_name=''):
    """
    Generate SKU in format {PREFIX}-{NNNN}, scoped per store + prefix.
    PREFIX comes from category.sku_prefix, then category name consonants,
    then product name consonants.
    """
    from .models import Product

    if category and category.sku_prefix:
        prefix = category.sku_prefix.upper()
    elif category and category.name:
        prefix = _extract_prefix(category.name)
    elif product_name:
        prefix = _extract_prefix(product_name)
    else:
        prefix = 'GEN'

    existing = (
        Product.objects.filter(store=store, sku__startswith=prefix + '-')
        .values_list('sku', flat=True)
    )
    max_num = 0
    for sku in existing:
        try:
            num = int(sku.split('-')[-1])
            max_num = max(max_num, num)
        except (ValueError, IndexError):
            pass

    return f"{prefix}-{max_num + 1:04d}"
