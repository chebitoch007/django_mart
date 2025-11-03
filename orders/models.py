# orders/models.py - ENHANCED VERSION

from django.conf import settings
from django.db import models, transaction
from django.db.models import Sum, F
from django.core.validators import MinValueValidator, RegexValidator
from django.core.exceptions import ValidationError
from django.utils import timezone
from django_countries.fields import CountryField
from djmoney.models.fields import MoneyField
from djmoney.money import Money
from store.models import Product
from store.aliexpress import fulfill_order
from .constants import ORDER_STATUS_CHOICES, PAYMENT_METHODS
import logging

logger = logging.getLogger(__name__)


class OrderManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset()


class Order(models.Model):
    """
    Enhanced Order model with comprehensive shipping and billing fields.
    Supports multi-currency transactions via django-money.
    """

    # User relationship
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='orders',
        null=True,
        blank=True
    )

    # Personal information
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    email = models.EmailField()

    # Phone number with validation (international format)
    phone_regex = RegexValidator(
        regex=r'^\+?1?\d{9,15}$',
        message="Phone number must be in format: '+999999999'. Up to 15 digits allowed."
    )
    phone = models.CharField(
        validators=[phone_regex],
        max_length=20,
        help_text="International format: +254712345678"
    )

    # Shipping address fields
    address = models.CharField(
        max_length=250,
        help_text="Street address or P.O. Box"
    )
    city = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20)
    state = models.CharField(
        max_length=100,
        blank=True,
        help_text="State/Province/Region (optional)"
    )
    country = CountryField(
        blank_label='(select country)',
        default='KE',
        help_text="Shipping destination country"
    )

    # NEW: Delivery instructions field
    delivery_instructions = models.CharField(
        max_length=200,
        blank=True,
        help_text="Special delivery notes (e.g., 'Leave at door', 'Call on arrival')"
    )

    # NEW: Billing same as shipping checkbox
    billing_same_as_shipping = models.BooleanField(
        default=True,
        help_text="Use shipping address for billing"
    )

    # Order metadata
    created = models.DateTimeField(auto_now_add=True, db_index=True)
    updated = models.DateTimeField(auto_now=True)

    status = models.CharField(
        max_length=20,
        choices=ORDER_STATUS_CHOICES,
        default='PENDING',
        db_index=True
    )

    payment_method = models.CharField(
        max_length=20,
        blank=True,
        choices=PAYMENT_METHODS,
        db_index=True
    )

    # Money field for order total
    total = MoneyField(
        max_digits=10,
        decimal_places=2,
        default_currency=settings.DEFAULT_CURRENCY,
        default=0.00
    )

    objects = OrderManager()

    class Meta:
        ordering = ('-created',)
        indexes = [
            models.Index(fields=['-created']),
            models.Index(fields=['status']),
            models.Index(fields=['user', 'status']),
        ]
        verbose_name = "Order"
        verbose_name_plural = "Orders"

    def __str__(self):
        return f"Order #{self.id} - {self.get_full_name()} ({self.status})"

    def get_full_name(self):
        """Returns the customer's full name"""
        return f"{self.first_name} {self.last_name}"

    @property
    def total_cost(self):
        """Calculate total cost from order items"""
        from decimal import Decimal

        items = self.items.all()
        if not items:
            return Money(0, self.total.currency)

        total = Decimal('0.00')
        for item in items:
            item_total = item.price.amount * item.quantity
            total += item_total

        return Money(total, self.total.currency)

    @property
    def is_payable(self):
        """Check if order can still be paid (within expiry period)"""
        return (
                self.status == 'PENDING'
                and (timezone.now() - self.created).days < settings.ORDER_EXPIRY_DAYS
        )

    @transaction.atomic
    def mark_as_paid(self, payment_method: str):
        """
        Mark order as paid with proper validation and idempotency.
        Thread-safe implementation using select_for_update.
        """
        # Reload from database with lock to prevent race conditions
        order = Order.objects.select_for_update().get(pk=self.pk)

        # If already paid, just log and return (idempotent)
        if order.status == 'PAID':
            logger.info(f"Order {order.id} already marked as PAID, skipping")
            return

        # Only allow transition from PENDING or PROCESSING
        if order.status not in ['PENDING', 'PROCESSING']:
            raise ValidationError(f"Order cannot be paid from {order.status} status")

        # Verify stock availability
        for item in order.items.select_for_update().select_related('product'):
            product = item.product
            if product.stock < item.quantity:
                raise ValidationError(f"Insufficient stock for {product.name}")

        # Update order status
        order.status = 'PAID'
        order.payment_method = payment_method
        order.save(update_fields=['status', 'payment_method', 'updated'])

        logger.info(f"Order {order.id} marked as PAID via {payment_method}")

    @transaction.atomic
    def cancel_order(self, reason=None):
        """
        Cancel order and restore product stock.
        """
        if self.status not in ['PENDING', 'PAID']:
            raise ValidationError(f"Order cannot be cancelled from {self.status} status")

        # Restore stock for all items
        for item in self.items.select_for_update().select_related('product'):
            Product.objects.filter(pk=item.product.pk).update(
                stock=F('stock') + item.quantity
            )

        self.status = 'CANCELLED'
        self.save(update_fields=['status', 'updated'])
        logger.info(f"Order {self.id} cancelled. Stock restored.")

    def clean(self):
        """
        Model-level validation (called explicitly, not on every save).
        """
        super().clean()

        # Validate phone number format
        if self.phone and not self.phone.startswith('+'):
            raise ValidationError({
                'phone': 'Phone number should start with country code (e.g., +254)'
            })

    def process_dropship_orders(self):
        """
        Process dropshipping orders via external fulfillment service.
        """
        results = []
        for item in self.items.filter(product__is_dropship=True):
            success, message = fulfill_order(item)
            results.append({
                'product': item.product.name,
                'success': success,
                'message': message
            })
        return results


class OrderItem(models.Model):
    """
    Individual item within an order.
    Stores snapshot of product price at time of purchase.
    """
    order = models.ForeignKey(
        Order,
        related_name='items',
        on_delete=models.CASCADE
    )
    product = models.ForeignKey(
        Product,
        related_name='order_items',
        on_delete=models.CASCADE
    )
    price = MoneyField(
        max_digits=10,
        decimal_places=2,
        default_currency=settings.DEFAULT_CURRENCY,
        validators=[MinValueValidator(0.01)],
        default=0.00,
        help_text="Price per unit at time of purchase"
    )
    quantity = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        help_text="Number of units ordered"
    )

    class Meta:
        verbose_name = "Order Item"
        verbose_name_plural = "Order Items"

    def __str__(self):
        return f"{self.quantity}x {self.product.name} (Order #{self.order.id})"

    @property
    def total_price(self):
        """Calculate total price for this line item"""
        return self.price * self.quantity