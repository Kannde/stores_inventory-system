import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from core.models import Store, StoreSettings
from inventory.models import Product


@override_settings(ALLOWED_HOSTS=['testserver', 'stores.afrotechlab.com'])
class SkrodaCheckoutTests(TestCase):
    checkout_url = 'https://skroda.com/pay/cs_test-token'

    def setUp(self):
        self.user = get_user_model().objects.create_user(username='owner', password='test-pass')
        self.store = Store.objects.create(
            name='Kokobox',
            owner=self.user,
            phone='0240000000',
            currency_symbol='GHS',
        )
        StoreSettings.objects.create(
            store=self.store,
            skroda_enabled=True,
            skroda_secret_key='sk_test_server_only',
            skroda_seller_phone='0240000000',
        )
        self.product = Product.objects.create(
            store=self.store,
            name='Test Product',
            unit_price='25.00',
            stock_qty=3,
        )
        self.client.force_login(self.user)

    @patch('payments.service._call')
    def test_checkout_sends_buyer_and_returns_tokenized_checkout_url(self, call_skroda):
        call_skroda.return_value = (True, {
            'id': 'txn_test',
            'checkout_url': self.checkout_url,
        })

        response = self.client.post(
            reverse('sales:api_checkout', kwargs={'store_slug': self.store.slug}),
            data=json.dumps({
                'items': [{
                    'id': str(self.product.id),
                    'type': 'product',
                    'quantity': 1,
                    'unit_price': '25.00',
                }],
                'payment_method': 'escrow',
                'customer_name': 'Ada Buyer',
                'customer_phone': '0241111111',
                'customer_email': 'ada@example.com',
            }),
            content_type='application/json',
            HTTP_HOST='stores.afrotechlab.com',
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['checkout_url'], self.checkout_url)
        method, path, secret_key, payload = call_skroda.call_args.args
        self.assertEqual((method, path), ('POST', '/transactions'))
        self.assertEqual(secret_key, 'sk_test_server_only')
        self.assertEqual(payload['success_url'], 'https://stores.afrotechlab.com/s/kokobox/sales/new/')
        self.assertEqual(payload['cancel_url'], 'https://stores.afrotechlab.com/s/kokobox/sales/new/')
        self.assertEqual(payload['buyer'], {
            'phone': '0241111111',
            'name': 'Ada Buyer',
            'email': 'ada@example.com',
        })

    def test_new_sale_embeds_backend_checkout_url_without_rewriting_it(self):
        response = self.client.get(
            reverse('sales:new_sale', kwargs={'store_slug': self.store.slug}),
        )

        self.assertContains(response, 'SkrodaCheckout.open(data.checkout_url')
        self.assertContains(response, 'iframe.src = checkoutUrl;')
        self.assertNotContains(response, '/quick-buy')

    def test_checkout_requires_complete_skroda_buyer_details(self):
        response = self.client.post(
            reverse('sales:api_checkout', kwargs={'store_slug': self.store.slug}),
            data=json.dumps({
                'items': [{'id': str(self.product.id), 'type': 'product', 'quantity': 1}],
                'payment_method': 'escrow',
                'customer_name': 'Ada Buyer',
                'customer_phone': '0241111111',
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error'], 'Customer name, phone, and email are required for escrow payments.')
