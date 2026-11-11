from django.test import TestCase
from django.urls import reverse

from .forms import StoreBrandingForm
from .models import StoreBranding
from .policies import POLICIES


class PolicyTests(TestCase):
    def test_public_defaults_and_persistent_footer_links(self):
        for slug, (title, text) in POLICIES.items():
            url = reverse('demos:store:policy', args=[slug])
            response = self.client.get(url)
            self.assertContains(response, '<h1>' + title + '</h1>', html=True)
            self.assertContains(response, text.split('\n')[0])
            self.assertContains(self.client.get(reverse('demos:store:home')), url)
        self.assertFalse(StoreBranding.objects.exists())
        self.assertEqual(self.client.get(reverse('demos:store:policy', args=['unknown'])).status_code, 404)

    def test_configured_policy_escapes_markup_and_uses_contact(self):
        StoreBranding.objects.create(returns_policy='<script>alert(1)</script>\n\nCustom returns',
                                     contact_email='help@example.com')
        response = self.client.get(reverse('demos:store:policy', args=['returns']))
        self.assertContains(response, '&lt;script&gt;')
        self.assertNotContains(response, '<script>alert(1)</script>')
        self.assertContains(response, 'mailto:help@example.com')
        self.assertNotContains(response, 'We do not offer change-of-mind refunds.')
        self.assertContains(self.client.get(reverse('demos:store:policy', args=['shipping'])),
                            'within 3 business days')

    def test_policy_fields_are_editable_and_blank_uses_default(self):
        for slug in POLICIES:
            self.assertIn(slug + '_policy', StoreBrandingForm().fields)
        StoreBranding.objects.create(shipping_policy='   ')
        self.assertContains(self.client.get(reverse('demos:store:policy', args=['shipping'])),
                            'within 3 business days')
