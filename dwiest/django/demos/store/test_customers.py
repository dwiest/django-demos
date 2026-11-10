from django.contrib.auth import get_user_model
from django.core import mail, signing
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import CustomerAddress


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', DEFAULT_FROM_EMAIL='store@example.com')
class CustomerTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('one@example.com', 'one@example.com', 'secret')
        self.other = get_user_model().objects.create_user('two@example.com', 'two@example.com', 'secret')
        self.url = reverse('demos:store:account')

    def test_requires_login_and_private_cache(self):
        self.assertEqual(self.client.get(self.url).status_code, 302)
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertIn('no-store', response['Cache-Control'])
        self.assertEqual(self.client.get(reverse('demos:store:customer_orders')).status_code, 200)

    def test_address_ownership(self):
        entry = CustomerAddress.objects.create(user=self.other, name='Other', line1='1 Main', city='Raleigh', state='NC', postal_code='27601')
        self.client.force_login(self.user)
        url = reverse('demos:store:customer_address', args=[entry.pk])
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.post(url, {'action': 'delete'}).status_code, 404)
        self.assertTrue(CustomerAddress.objects.filter(pk=entry.pk).exists())

    def test_email_requires_password_and_confirmation(self):
        self.client.force_login(self.user)
        self.client.post(self.url, {'action': 'email', 'email': 'new@example.com', 'password': 'wrong'})
        self.assertEqual(len(mail.outbox), 0)
        self.client.post(self.url, {'action': 'email', 'email': 'new@example.com', 'password': 'secret'})
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, 'one@example.com')
        link = mail.outbox[0].body.split('http://testserver')[1]
        self.assertEqual(self.client.get(link).status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, 'one@example.com')
        self.assertEqual(self.client.post(link).status_code, 302)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, 'new@example.com')
        self.assertEqual(self.user.username, 'new@example.com')
        self.assertContains(self.client.post(link), 'expired or unavailable')

    def test_duplicate_email_is_rejected(self):
        self.client.force_login(self.user)
        response = self.client.post(self.url, {'action': 'email', 'email': self.other.email, 'password': 'secret'})
        self.assertContains(response, 'unavailable')
        self.assertEqual(len(mail.outbox), 0)

class CustomerOrderTests(TestCase):
    from .test_orders import OrderTests
    url = OrderTests.url
    place = OrderTests.place

    def setUp(self):
        self.OrderTests.setUp(self)

    def test_history_is_scoped_to_owner(self):
        order = self.place()
        user = get_user_model().objects.create_user('customer', 'buyer@example.com', 'secret')
        self.client.force_login(user)
        detail = reverse('demos:store:customer_order', args=[order.pk])
        self.assertEqual(self.client.get(detail).status_code, 404)
        order.user = user
        order.status = 'processing'
        order.save()
        self.assertContains(self.client.get(detail), 'Processing')
        self.assertContains(self.client.get(reverse('demos:store:customer_orders')), order.number)
        other = get_user_model().objects.create_user('other', 'other@example.com', 'secret')
        self.client.force_login(other)
        self.assertEqual(self.client.get(detail).status_code, 404)

    def test_saved_address_does_not_change_order_snapshot(self):
        user = get_user_model().objects.create_user('customer', 'buyer@example.com', 'secret')
        self.client.force_login(user)
        entry = CustomerAddress.objects.create(user=user, name='Buyer', line1='Saved street', city='Raleigh', state='NC', postal_code='27601')
        response = self.client.get(self.url('checkout') + '?address=' + str(entry.pk))
        self.assertEqual(response.context['form'].initial['line1'], 'Saved street')
        order = self.place()
        original = order.shipping_address.line1
        response = self.client.post(reverse('demos:store:customer_address', args=[entry.pk]),
                                    dict(name='Buyer', line1='Changed street', city='Raleigh', state='NC', postal_code='27601'))
        self.assertEqual(response.status_code, 302)
        order.shipping_address.refresh_from_db()
        self.assertEqual(order.shipping_address.line1, original)
