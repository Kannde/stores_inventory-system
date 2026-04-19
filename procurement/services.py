from django.db import transaction
from django.utils import timezone
from inventory.models import StockMovement, Supplier
from inventory.sku import generate_sku


@transaction.atomic
def fulfil_plan(plan):
    created = restocked = skipped = 0
    needs_images = []  # list of (product, is_new)

    for item in plan.items.select_related('product', 'category').all():
        if not item.is_fulfilled:
            skipped += 1
            continue

        qty = item.actual_qty or item.planned_qty

        if item.product:
            # Restock existing product — only increment stock qty
            prod = item.product
            prod.stock_qty += qty
            prod.save(update_fields=['stock_qty'])

            StockMovement.objects.create(
                product=prod, movement_type='in',
                quantity=qty,
                reason=f'Procurement: {plan.title}',
                reference=str(plan.id),
            )
            restocked += 1

            if not prod.images.exists():
                needs_images.append({'id': str(prod.id), 'name': prod.name, 'is_new': False})

        else:
            # Create brand-new product
            cost = item.actual_unit_cost or item.estimated_unit_cost
            supplier_obj = None
            if item.supplier_name:
                supplier_obj, _ = Supplier.objects.get_or_create(
                    store=plan.store, name=item.supplier_name,
                    defaults={'ownership': 'external'},
                )

            from inventory.models import Product
            prod = Product(
                store=plan.store,
                name=item.new_product_name,
                category=item.category,
                supplier=supplier_obj,
                stock_qty=qty,
                cost_price=cost or 0,
                unit_price=item.selling_price or 0,
                is_paid=item.is_paid,
                available_for_preorder=item.available_for_preorder,
            )
            prod.save()
            prod.sku = generate_sku(plan.store, item.category, item.new_product_name)
            prod.save(update_fields=['sku'])

            StockMovement.objects.create(
                product=prod, movement_type='in',
                quantity=qty,
                reason=f'Procurement: {plan.title}',
                reference=str(plan.id),
            )

            item.product = prod
            item.save(update_fields=['product'])
            created += 1
            needs_images.append({'id': str(prod.id), 'name': prod.name, 'is_new': True})

    plan.status = 'fulfilled'
    plan.fulfilled_at = timezone.now()
    plan.save(update_fields=['status', 'fulfilled_at'])

    return {'created': created, 'restocked': restocked, 'skipped': skipped, 'needs_images': needs_images}
