import hashlib
import hmac
import json

from django.db import transaction as db_transaction
from django.db.models import F
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from core.models import Store, StoreSettings
from inventory.models import Product, StockMovement
from sales.models import Sale

from .models import SkrodaTransaction, SkrodaWebhookEvent


def _verify_signature(raw_body: bytes, signature_header: str, secret: str) -> bool:
    expected = 'sha256=' + hmac.new(
        secret.encode(),
        raw_body,
        hashlib.sha256,
    ).hexdigest()
    try:
        return hmac.compare_digest(signature_header, expected)
    except TypeError:
        return False


@csrf_exempt
@require_POST
def skroda_webhook(request, store_slug):
    store = get_object_or_404(Store, slug=store_slug)
    try:
        store_settings = store.settings
    except StoreSettings.DoesNotExist:
        return HttpResponse('Not configured', status=400)

    if not store_settings.skroda_enabled or not store_settings.skroda_webhook_secret:
        return HttpResponse('Not configured', status=400)

    raw_body = request.body
    signature = request.headers.get('X-Skroda-Signature', '')

    if not _verify_signature(raw_body, signature, store_settings.skroda_webhook_secret):
        return HttpResponse('Invalid signature', status=400)

    try:
        event = json.loads(raw_body)
    except json.JSONDecodeError:
        return HttpResponse('Invalid JSON', status=400)

    event_id = event.get('id', '')
    event_type = event.get('type', '')

    # Idempotency — ignore events we've already processed
    if SkrodaWebhookEvent.objects.filter(event_id=event_id).exists():
        return HttpResponse('OK', status=200)

    SkrodaWebhookEvent.objects.create(
        event_id=event_id,
        event_type=event_type,
        store=store,
        payload=event,
    )

    _handle_event(event_type, event.get('data', {}))

    return HttpResponse('OK', status=200)


def _handle_event(event_type, data):
    # transaction.agent_unavailable has a flat payload (transaction_id, not transaction.id)
    if event_type == 'transaction.agent_unavailable':
        skroda_id = data.get('transaction_id', '')
        if skroda_id:
            try:
                skroda_txn = SkrodaTransaction.objects.get(skroda_id=skroda_id)
                skroda_txn.status = 'agent_unavailable'
                skroda_txn.save(update_fields=['status', 'updated_at'])
            except SkrodaTransaction.DoesNotExist:
                pass
        return

    txn_data = data.get('transaction', {})
    skroda_id = txn_data.get('id', '')
    if not skroda_id:
        return

    try:
        skroda_txn = SkrodaTransaction.objects.select_related('sale').get(skroda_id=skroda_id)
    except SkrodaTransaction.DoesNotExist:
        return

    sale = skroda_txn.sale

    if event_type == 'transaction.funded':
        with db_transaction.atomic():
            skroda_txn.status = 'funded'
            skroda_txn.save(update_fields=['status', 'updated_at'])
            Sale.objects.filter(pk=sale.pk, status='pending_payment').update(
                status='completed',
                amount_paid=skroda_txn.amount,
            )

    elif event_type == 'transaction.completed':
        skroda_txn.status = 'completed'
        skroda_txn.save(update_fields=['status', 'updated_at'])

    elif event_type in ('transaction.cancelled', 'transaction.refunded'):
        with db_transaction.atomic():
            skroda_txn.status = 'cancelled' if event_type == 'transaction.cancelled' else 'refunded'
            skroda_txn.save(update_fields=['status', 'updated_at'])
            if sale.status == 'pending_payment':
                _restore_stock(sale)
                Sale.objects.filter(pk=sale.pk).update(status='refunded')

    elif event_type == 'transaction.disputed':
        skroda_txn.status = 'disputed'
        skroda_txn.save(update_fields=['status', 'updated_at'])

    else:
        status_map = {
            'transaction.negotiation': 'negotiation',
            'transaction.agreed': 'agreed',
            'transaction.shipped': 'shipped',
            'transaction.agent_received': 'agent_received',
            'transaction.delivered': 'delivered',
        }
        new_status = status_map.get(event_type)
        if new_status:
            skroda_txn.status = new_status
            skroda_txn.save(update_fields=['status', 'updated_at'])


def _restore_stock(sale):
    """Re-add stock deducted for a pending_payment sale that was cancelled/refunded."""
    for item in sale.items.select_related('product', 'package').all():
        if item.product_id:
            Product.objects.filter(pk=item.product_id).update(
                stock_qty=F('stock_qty') + item.quantity
            )
            StockMovement.objects.create(
                product=item.product,
                movement_type='adjustment',
                quantity=item.quantity,
                reference=f"escrow_cancel:{sale.id}",
            )
        elif item.package_id:
            for pi in item.package.items.select_related('product').all():
                restored = pi.quantity * item.quantity
                Product.objects.filter(pk=pi.product_id).update(
                    stock_qty=F('stock_qty') + restored
                )
                StockMovement.objects.create(
                    product=pi.product,
                    movement_type='adjustment',
                    quantity=restored,
                    reference=f"escrow_cancel:{sale.id}",
                )


def payment_success(request, store_slug, sale_id):
    store = get_object_or_404(Store, slug=store_slug)
    sale = get_object_or_404(Sale, pk=sale_id, store=store)
    skroda_txn = getattr(sale, 'skroda_transaction', None)
    return render(request, 'payments/success.html', {
        'store': store,
        'sale': sale,
        'skroda_txn': skroda_txn,
    })


def payment_cancelled(request, store_slug, sale_id):
    store = get_object_or_404(Store, slug=store_slug)
    sale = get_object_or_404(Sale, pk=sale_id, store=store)
    return render(request, 'payments/cancelled.html', {
        'store': store,
        'sale': sale,
    })
