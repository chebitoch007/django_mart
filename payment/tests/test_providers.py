from django.test import TestCase, override_settings
from unittest.mock import patch
from .models import Payment, Order
from .providers import StripeProvider


class StripeProviderTest(TestCase):
    @override_settings(STRIPE_SECRET_KEY='test_key')
    def test_initiate_payment_success(self):
        order = Order.objects.create(total=100.00)
        payment = Payment.objects.create(
            order=order,
            amount=100.00,
            currency='USD',
            method='STRIPE'
        )

        with patch('stripe.PaymentIntent.create') as mock_create:
            mock_create.return_value = {'client_secret': 'test_secret'}
            provider = StripeProvider(payment)
            result = provider.initiate_payment()

            self.assertTrue('client_secret' in result)
            self.assertEqual(result['client_secret'], 'test_secret')

    def test_initiate_payment_failure(self):
        # Similar test for failure cases
        pass