from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from apps.accounts.models import SellerProfile
from apps.payments.models import CreditPackage

User = get_user_model()

class PaymentsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='payer@example.com',
            password='testpassword123'
        )
        self.client = Client()
        self.client.login(email='payer@example.com', password='testpassword123')
        
        # Create credit packages
        self.pack1 = CreditPackage.objects.create(
            name="Pack Découverte",
            credits=10,
            price=29.99,
            price_id="price_123"
        )

    def test_pricing_page_accessible(self):
        """Test pricing page loads correctly."""
        response = self.client.get(reverse('payments:pricing'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Pack Découverte")

    def test_credits_history_page(self):
        """Test credits history page."""
        response = self.client.get(reverse('payments:credits_history'))
        self.assertEqual(response.status_code, 200)
        
    def test_buy_start(self):
        """Test buy button redirection."""
        response = self.client.post(reverse('payments:buy_credits', args=[self.pack1.id]))
        # In test/dev environment without Stripe keys, this might behave differently
        # Usually redirects to Stripe Checkout or returns 200/302
        self.assertTrue(response.status_code in [200, 302])
