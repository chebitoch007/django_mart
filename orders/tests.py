# orders/tests.py
from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse

from cart.models import Cart
from .models import Order, Payment


class PaymentInitializationTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass'
        )
        self.cart = Cart.objects.create(user=self.user)

    def test_payment_creation(self):
        # Simulate order creation
        self.client.login(username='testuser', password='testpass')
        response = self.client.post(reverse('orders:order_create'), {
            'first_name': 'John',
            'last_name': 'Doe',
            'email': 'john@example.com',
            'address': '123 Main St',
            'postal_code': '12345',
            'city': 'Nairobi'
        })

        # Verify order and payment were created
        order = Order.objects.first()
        self.assertIsNotNone(order)
        self.assertIsNotNone(order.order_payment)
        self.assertEqual(order.order_payment.status, 'PENDING')
        self.assertEqual(order.order_payment.amount, self.cart.total_price)
