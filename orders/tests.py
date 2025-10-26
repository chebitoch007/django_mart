# orders/tests.py

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from decimal import Decimal

# --- Import models ---
from cart.models import Cart
from store.models import Product, Category
from .models import Order
from payment.models import Payment

User = get_user_model()  # This is the key fix!


class PaymentInitializationTest(TestCase):
    def setUp(self):
        # Use get_user_model() instead of User.objects directly
        self.user = User.objects.create_user(
            email='testuser@example.com',  # Use email as primary
            password='testpass123!@#',  # Strong password
            first_name='Test',
            last_name='User'
        )
        self.cart = Cart.objects.create(user=self.user)

        # --- Create a product and add it to the cart ---
        self.category = Category.objects.create(name='Test Cat', slug='test-cat')
        self.product = Product.objects.create(
            name='Test Product',
            slug='test-product',
            price=Decimal('100.00'),
            stock=10,
            category=self.category
        )
        self.cart.items.create(product=self.product, quantity=2)
        # --- Cart total is now 200.00 ---

    def test_payment_creation(self):
        # Simulate order creation
        self.client.login(email='testuser@example.com', password='testpass123!@#')

        shipping_data = {
            'first_name': 'John',
            'last_name': 'Doe',
            'email': 'john@example.com',
            'phone': '+254700000000',
            'address': '123 Main St',
            'postal_code': '12345',
            'city': 'Nairobi',
            'country': 'KE'
        }

        response = self.client.post(reverse('orders:create_order'), shipping_data)

        # Check that it redirected to the checkout page
        self.assertRedirects(response, reverse('orders:checkout'))

        # Verify order and payment were created
        self.assertEqual(Order.objects.count(), 1)
        order = Order.objects.first()

        self.assertIsNotNone(order)
        self.assertEqual(order.user, self.user)
        self.assertEqual(order.total, Decimal('200.00'))  # 2 * 100.00

        # Check the payment
        self.assertIsNotNone(order.payment)
        self.assertEqual(order.payment.status, 'PENDING')
        self.assertEqual(order.payment.amount, Decimal('200.00'))

        # Verify cart was cleared
        self.cart.refresh_from_db()
        self.assertEqual(self.cart.items.count(), 0)