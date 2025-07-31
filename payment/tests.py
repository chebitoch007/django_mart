# payment/tests.py
from django.test import TestCase
from django.urls import reverse

from orders.models import Order
from payment.models import Payment


class PaymentInitializationTest(TestCase):
    def test_payment_auto_creation(self):
        order = Order.objects.create(
            user=self.user,
            total_price=100.00,
            currency='KES'
        )
        self.assertTrue(hasattr(order, 'payment'))
        self.assertEqual(order.order_payment.status, 'PENDING')
        self.assertEqual(order.order_payment.amount, 100.00)

    def test_payment_processing_flow(self):
        order = Order.objects.create(...)
        # Simulate payment request
        response = self.client.post(reverse('payment:process_payment'), {
            'order_id': order.id,
            'payment_method': 'mpesa',
            'amount': order.total_price,
            'currency': order.currency,
            'phone_number': '712345678'
        })
        self.assertEqual(response.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.order_payment.status, 'COMPLETED')