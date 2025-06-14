from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db import transaction
from store.models import Product
from django.db.models import Sum, F
from .constants import ORDER_STATUS_CHOICES, PAYMENT_METHODS, CURRENCY_CHOICES


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
        return OrderQuerySet(self.model, using=self._db).select_related('user').prefetch_related('items__product')

    def create_from_cart(self, cart, user, shipping_details):
        with transaction.atomic():
            order = self.create(
                user=user,
                **shipping_details,
                currency=settings.DEFAULT_CURRENCY
            )

            items = []
            for cart_item in cart.items.select_related('product').all():
                if cart_item.quantity > cart_item.product.stock:
                    raise ValidationError(f"Insufficient stock for {cart_item.product.name}")

                items.append(OrderItem(
                    order=order,
                    product=cart_item.product,
                    price=cart_item.product.price,
                    quantity=cart_item.quantity
                ))

                Product.objects.filter(pk=cart_item.product.pk).update(
                    stock=F('stock') - cart_item.quantity
                )

            OrderItem.objects.bulk_create(items)
            cart.items.all().delete()
            return order


class Order(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL,
                             on_delete=models.CASCADE,
                             related_name='orders')
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    email = models.EmailField()
    address = models.CharField(max_length=250)
    postal_code = models.CharField(max_length=20)
    city = models.CharField(max_length=100)
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

    @property
    def total_cost(self):
        return self.items.aggregate(
            total=Sum(F('price') * F('quantity'), output_field=models.DecimalField())
        )['total'] or 0

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def is_payable(self):
        return (
            self.status == 'PENDING' and
            (timezone.now() - self.created).days < settings.ORDER_EXPIRY_DAYS
        )

    @transaction.atomic
    def mark_as_paid(self, payment_method: str):
        if self.status != 'PENDING':
            raise ValidationError("Order cannot be paid in current state")

        with transaction.atomic():
            for item in self.items.select_for_update().select_related('product'):
                product = item.product
                if product.stock < item.quantity:
                    raise ValidationError(
                        f"Insufficient stock for {product.name}"
                    )

            self.status = 'PAID'
            self.payment_method = payment_method
            self.save(update_fields=['status', 'payment_method', 'updated'])

    @transaction.atomic
    def cancel_order(self, reason=None):
        valid_statuses = ['PENDING', 'PAID']
        if self.status not in valid_statuses:
            raise ValidationError(f"Order cannot be cancelled from {self.status} status")

        with transaction.atomic():
            for item in self.items.select_for_update().select_related('product'):
                Product.objects.filter(pk=item.product.pk).update(
                    stock=F('stock') + item.quantity
                )

            self.status = 'CANCELLED'
            self.save(update_fields=['status', 'updated'])


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

    def clean(self):
        if self._state.adding:
            if self.price != self.product.price:
                raise ValidationError({
                    'price': 'Price must match current product price'
                })
            if self.quantity > self.product.stock:
                raise ValidationError({
                    'quantity': 'Quantity exceeds available stock'
                })

    def save(self, *args, **kwargs):
        if not self._state.adding:
            original = OrderItem.objects.get(pk=self.pk)
            if self.price != original.price:
                raise ValidationError("Cannot modify price of existing item")
        super().save(*args, **kwargs)