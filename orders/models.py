#orders/models.py

from django.conf import settings
from django.db import models, transaction
from django.db.models import Sum, F
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from django.utils import timezone
from django_countries.fields import CountryField
from djmoney.models.fields import MoneyField
from djmoney.money import Money
from store.models import Product
from store.aliexpress import fulfill_order
from .constants import ORDER_STATUS_CHOICES, PAYMENT_METHODS


class OrderManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset()


class Order(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='orders',
        null=True,
        blank=True
    )
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    email = models.EmailField()
    address = models.CharField(max_length=250)
    postal_code = models.CharField(max_length=20)
    state = models.CharField(max_length=100, blank=True)
    country = CountryField(blank_label='(select country)', default='KE')
    city = models.CharField(max_length=100)
    phone = models.CharField(max_length=20, blank=True)
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

    def __str__(self):
        return f"Order #{self.id} - {self.get_full_name()} ({self.status})"

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def total_cost(self):
        total_sum = self.items.aggregate(
            total=Sum(F('price_amount') * F('quantity'))
        )['total'] or 0
        return Money(total_sum, self.total.currency)

    @property
    def is_payable(self):
        return (
            self.status == 'PENDING'
            and (timezone.now() - self.created).days < settings.ORDER_EXPIRY_DAYS
        )

    @transaction.atomic
    def mark_as_paid(self, payment_method: str):
        if self.status != 'PENDING':
            raise ValidationError("Order cannot be paid in current state")

        for item in self.items.select_for_update().select_related('product'):
            product = item.product
            if product.stock < item.quantity:
                raise ValidationError(f"Insufficient stock for {product.name}")

        self.status = 'PAID'
        self.payment_method = payment_method
        self.save(update_fields=['status', 'payment_method', 'updated'])

    @transaction.atomic
    def cancel_order(self, reason=None):
        if self.status not in ['PENDING', 'PAID']:
            raise ValidationError(f"Order cannot be cancelled from {self.status} status")

        for item in self.items.select_for_update().select_related('product'):
            Product.objects.filter(pk=item.product.pk).update(
                stock=F('stock') + item.quantity
            )

        self.status = 'CANCELLED'
        self.save(update_fields=['status', 'updated'])

    def save(self, *args, **kwargs):
        if self.pk:
            original = Order.objects.select_related('payment').get(pk=self.pk)
            if hasattr(original, 'payment') and original.payment.status != 'PENDING':
                raise PermissionError("Order has already been processed")
        super().save(*args, **kwargs)

    def clean(self):
        if self.pk:
            original = Order.objects.select_related('payment').get(pk=self.pk)
            if hasattr(original, 'payment') and original.payment.status != 'PENDING':
                raise ValidationError("Cannot modify a paid or processing order")

    def process_dropship_orders(self):
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
    order = models.ForeignKey(Order, related_name='items', on_delete=models.CASCADE)
    #product = models.ForeignKey(Product, related_name='order_items', on_delete=models.PROTECT)
    product = models.ForeignKey(Product, related_name='order_items', on_delete=models.CASCADE)
    price = MoneyField(
        max_digits=10,
        decimal_places=2,
        default_currency=settings.DEFAULT_CURRENCY,
        validators=[MinValueValidator(0.01)],
        default=0.00
    )
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])

    @property
    def total_price(self):
        return self.price * self.quantity
