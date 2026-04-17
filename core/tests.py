from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Store, StoreStaff


User = get_user_model()


class AuthFlowTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username='owner1', password='owner-pass-123')
        self.sales_user = User.objects.create_user(username='sales1', password='sales-pass-123')
        self.superuser = User.objects.create_superuser(
            username='admin1',
            email='admin@example.com',
            password='admin-pass-123',
        )

        self.store = Store.objects.create(name='Main Store', owner=self.owner)
        self.other_store = Store.objects.create(name='Other Store')
        StoreStaff.objects.create(
            store=self.store,
            user=self.sales_user,
            name='Sales Rep',
            role='sales',
            pin='1111',
        )

    def test_superuser_home_redirects_to_admin_landing(self):
        self.client.force_login(self.superuser)
        response = self.client.get(reverse('core:home'))
        self.assertRedirects(response, reverse('core:admin_landing'))

    def test_admin_landing_lists_stores(self):
        self.client.force_login(self.superuser)
        response = self.client.get(reverse('core:admin_landing'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Admin Landing')
        self.assertContains(response, self.store.name)

    def test_store_owner_login_redirects_to_store_dashboard(self):
        response = self.client.post(reverse('core:login'), {
            'username': 'owner1',
            'password': 'owner-pass-123',
        })
        self.assertRedirects(
            response,
            reverse('core:store_dashboard', kwargs={'store_slug': self.store.slug}),
        )

    def test_sales_login_redirects_to_store_dashboard(self):
        response = self.client.post(reverse('core:login'), {
            'username': 'sales1',
            'password': 'sales-pass-123',
        })
        self.assertRedirects(
            response,
            reverse('core:store_dashboard', kwargs={'store_slug': self.store.slug}),
        )

    def test_store_owner_can_update_store_settings(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse('core:store_settings', kwargs={'store_slug': self.store.slug}),
            {
                'name': 'Main Store Updated',
                'phone': '0240000000',
                'location': 'Accra',
                'description': 'Updated description',
                'currency_symbol': 'GHS',
            },
        )
        self.assertRedirects(
            response,
            reverse('core:store_settings', kwargs={'store_slug': self.store.slug}),
        )
        self.store.refresh_from_db()
        self.assertEqual(self.store.name, 'Main Store Updated')
        self.assertEqual(self.store.phone, '0240000000')

    def test_sales_user_cannot_access_another_store(self):
        self.client.force_login(self.sales_user)
        response = self.client.get(
            reverse('core:store_dashboard', kwargs={'store_slug': self.other_store.slug})
        )
        self.assertEqual(response.status_code, 403)
