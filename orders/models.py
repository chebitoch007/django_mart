#orders/models.py

from django_countries.fields import CountryField
from django.utils import timezone
from django.conf import settings
from django.db import models
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from django.db import transaction
from store.aliexpress import fulfill_order
from store.models import Product
from django.db.models import Sum, F
from .constants import ORDER_STATUS_CHOICES, CURRENCY_CHOICES, PAYMENT_METHODS


class OrderQuerySet(models.QuerySet):
    def for_user(self, user):
        return self.filter(user=user).select_related('user')

    def payable(self):
        return self.filter(
            status='PENDING',
            created__gte=timezone.now() - timezone.timedelta(days=settings.ORDER_EXPIRY_DAYS)
        ).prefetch_related('items')


class OrderManager(models.Manager):
    def get_queryset(self):
        # ✅ REMOVED prefetch_related - let views handle their own prefetching
        return OrderQuerySet(self.model, using=self._db).select_related('user')



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
    currency = models.CharField(
        max_length=3,
        choices=CURRENCY_CHOICES,
        default='KES'
    )
    payment_method = models.CharField(
        max_length=20,
        blank=True,
        choices=PAYMENT_METHODS,
        db_index=True
    )
    total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
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
        return self.items.aggregate(
            total=Sum(F('price') * F('quantity'), output_field=models.DecimalField())
        )['total'] or 0

    @property
    def is_payable(self):
        return (
                self.status == 'PENDING' and
                (timezone.now() - self.created).days < settings.ORDER_EXPIRY_DAYS
        )

    @transaction.atomic
    def mark_as_paid(self, payment_method: str):
        """Marks the order as paid if still pending and enough stock exists."""
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
        """Cancels the order and restores product stock."""
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
            # ✅ Safely check if 'payment' exists before accessing its status
            if hasattr(original, 'payment') and original.payment.status != 'PENDING':
                raise PermissionError("Order has already been processed")
        super().save(*args, **kwargs)

    def clean(self):
        if self.pk:
            original = Order.objects.select_related('payment').get(pk=self.pk)
            # ✅ Also apply the same safe check here
            if hasattr(original, 'payment') and original.payment.status != 'PENDING':
                raise ValidationError("Cannot modify a paid or processing order")

    def process_dropship_orders(self):
        """Trigger dropship fulfillment for all dropshipping items."""
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
    order = models.ForeignKey(
        Order,
        related_name='items',
        on_delete=models.CASCADE
    )
    product = models.ForeignKey(
        Product,
        related_name='order_items',
        on_delete=models.PROTECT
    )
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0.01)]
    )
    quantity = models.PositiveIntegerField(
        validators=[MinValueValidator(1)]
    )

    dropship_processed = models.BooleanField(default=False)
    dropship_order_id = models.CharField(max_length=100, blank=True)
    tracking_number = models.CharField(max_length=100, blank=True)
    estimated_delivery = models.CharField(max_length=50, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['order', 'product'],
                name='unique_order_product'
            ),
            models.CheckConstraint(
                check=models.Q(quantity__gte=1),
                name="min_order_item_quantity"
            )
        ]

    def __str__(self):
        return f"{self.quantity}x {self.product.name} @ {self.price}"

    @property
    def total_price(self):
        return self.price * self.quantity


    def mark_as_processed(self, order_id, tracking, delivery):
        self.dropship_processed = True
        self.dropship_order_id = order_id
        self.tracking_number = tracking
        self.estimated_delivery = delivery
        self.save()

    def fulfill(self):
        """Trigger fulfillment if it's a dropshipping product."""
        if not self.product.is_dropship:
            return False, "Not a dropshipping product"
        return fulfill_order(self)

    def save(self, *args, **kwargs):
        if not self._state.adding:
            original = OrderItem.objects.get(pk=self.pk)

            if self.price != original.price:
                if not self.product.is_dropship:
                    raise ValidationError("Cannot modify price of existing item")

        super().save(*args, **kwargs)


class CurrencyRate(models.Model):
    base_currency = models.CharField(max_length=3, choices=settings.CURRENCIES)
    target_currency = models.CharField(max_length=3, choices=settings.CURRENCIES)
    rate = models.DecimalField(max_digits=12, decimal_places=6)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('base_currency', 'target_currency')
        indexes = [
            models.Index(fields=['base_currency', 'target_currency']),
        ]

    def __str__(self):
        return f"{self.base_currency}/{self.target_currency}: {self.rate}"