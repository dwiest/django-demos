from unittest.mock import patch

from django.core import mail
from django.core.cache import cache
from django.test import Client, TestCase

from .guest_orders import make_token
from . import test_orders


class GuestOrderTests(TestCase):
    url = test_orders.OrderTests.url
    place = test_orders.OrderTests.place
    def setUp(self):
        test_orders.OrderTests.setUp(self)
        cache.clear()

    def test_email_link_works_in_new_browser_and_does_not_grant_other_orders(self):
        order = self.place()
        guest = Client()
        response = guest.post(self.url('guest_order_lookup'), {
            'order_number': order.number.lower(), 'email': order.email.upper()})
        self.assertContains(response, 'If the order number and email address match our records')
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(mail.outbox[-1].to, [order.email])
        import re
        link = re.search(r'https?://[^\s]+', mail.outbox[-1].body).group()
        response = guest.get(link)
        self.assertContains(response, order.number)
        self.assertContains(response, 'Wurm pin')
        self.assertIn('no-store', response['Cache-Control'])
        self.assertEqual(response['Referrer-Policy'], 'no-referrer')
        self.assertEqual(guest.get(self.url('order_complete', order.token)).status_code, 404)
        order.status = 'processing'
        order.save()
        self.assertContains(guest.get(link), 'Processing')

    def test_wrong_details_are_indistinguishable_and_send_nothing(self):
        order = self.place()
        guest = Client()
        valid = guest.post(self.url('guest_order_lookup'), {'order_number': order.number, 'email': order.email})
        count = len(mail.outbox)
        for number, email in [(order.number, 'wrong@example.com'), ('RW-99999999', order.email)]:
            response = guest.post(self.url('guest_order_lookup'), {'order_number': number, 'email': email})
            self.assertEqual(response.content, valid.content)
        self.assertEqual(len(mail.outbox), count)

    def test_invalid_expired_tampered_and_revoked_links(self):
        order = self.place()
        token = make_token(order)
        guest = Client()
        url = self.url('guest_order_detail', token)
        self.assertEqual(guest.get(url).status_code, 200)
        self.assertEqual(guest.get(url + 'x').status_code, 404)
        with patch('django.core.signing.time.time', return_value=0):
            expired = make_token(order)
        response = guest.get(self.url('guest_order_detail', expired))
        self.assertContains(response, 'Request a new link', status_code=404)
        self.assertNotContains(response, '123 Main St', status_code=404)
        order.email = 'changed@example.com'
        order.save()
        self.assertEqual(guest.get(url).status_code, 404)

    def test_rate_limit_csrf_and_delivery_failure(self):
        order = self.place()
        data = {'order_number': order.number, 'email': order.email}
        guest = Client()
        for _ in range(5):
            self.assertEqual(guest.post(self.url('guest_order_lookup'), data).status_code, 200)
        self.assertEqual(len(mail.outbox), 4)
        self.assertEqual(Client(enforce_csrf_checks=True).post(self.url('guest_order_lookup'), data).status_code, 403)
        cache.clear()
        with patch('dwiest.django.demos.store.views.send_mail', side_effect=RuntimeError('offline')):
            with self.assertLogs('dwiest.django.demos.store.views', level='ERROR'):
                self.assertContains(guest.post(self.url('guest_order_lookup'), data), 'If the order number and email address match our records')

    def test_configured_public_https_origin_is_used(self):
        from .models import StoreBranding
        StoreBranding.objects.create(email_shop_url='https://rotten.world/django/demos/store/')
        order = self.place()
        self.client.post(self.url('guest_order_lookup'), {'order_number': order.number, 'email': order.email})
        self.assertIn('https://rotten.world' + self.url('guest_order_lookup'), mail.outbox[-1].body)

    def test_https_lookup_form_preserves_csrf_referer_and_requires_token(self):
        guest = Client(enforce_csrf_checks=True)
        url = self.url('guest_order_lookup')
        response = guest.get(url, secure=True)
        self.assertEqual(response['Referrer-Policy'], 'same-origin')
        token = guest.cookies['csrftoken'].value
        data = {'order_number': 'RW-99999999', 'email': 'unknown@example.com',
                'csrfmiddlewaretoken': token}
        # Django 3.2 validates HTTPS Referer; newer versions also check Origin.
        headers = {'HTTP_REFERER': 'https://testserver' + url,
                   'HTTP_ORIGIN': 'https://testserver'}
        self.assertContains(guest.post(url, data, secure=True, **headers),
                            'If the order number and email address match our records')
        data.pop('csrfmiddlewaretoken')
        self.assertEqual(guest.post(url, data, secure=True, **headers).status_code, 403)

    def test_lookup_email_uses_full_shared_branding(self):
        from .models import StoreBranding
        StoreBranding.objects.create(name='Rotten.World', email_header='Hello <Wurm>',
            email_header_image_bucket='brand', email_header_image_key='header.png',
            email_footer_image_bucket='brand', email_footer_image_key='footer.png',
            email_footer_heading='Stay rotten', email_footer='Good stuff & questionable influences.',
            contact_email='help@example.com', email_shop_url='https://shop.example.com/',
            email_help_url='https://shop.example.com/help/', copyright_text='Copyright Rotten.World')
        order = self.place()
        with patch('dwiest.django.demos.store.media.permanent_url',
                   side_effect=lambda bucket, key: 'https://images.example.com/' + key):
            response = self.client.post(self.url('guest_order_lookup'),
                {'order_number': order.number, 'email': order.email})
        self.assertContains(response, 'Check your email')
        self.assertNotContains(response, 'No account needed')
        html = mail.outbox[-1].alternatives[0][0]
        for value in ['https://images.example.com/header.png', 'https://images.example.com/footer.png',
                      'Hello &lt;Wurm&gt;', 'Stay rotten', 'mailto:help@example.com',
                      'https://shop.example.com/help/', 'Copyright Rotten.World']:
            self.assertIn(value, html)
        self.assertIn('Good stuff & questionable influences.', mail.outbox[-1].body)
