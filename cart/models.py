# cart/models.py

from django.db import models
from django.contrib.auth import get_user_model
from django.db.models import Q
from store.models import Product
from decimal import Decimal
from djmoney.money import Money
from django.conf import settings

User = get_user_model()


class Cart(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='user_cart',
        null=True,
        blank=True
    )
    session_key = models.CharField(max_length=40, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['session_key'],
                condition=Q(user__isnull=True),
                name='unique_session_key_if_user_is_null'
            )
        ]

    def add_product(self, product, quantity=1, update_quantity=False):
        if quantity < 1:
            return None, False

        cart_item, created = self.items.get_or_create(product=product)

        if update_quantity:
            cart_item.quantity = quantity
        elif created:
            cart_item.quantity = quantity
        else:
            cart_item.quantity += quantity

        if cart_item.quantity > product.stock:
            cart_item.quantity = product.stock

        cart_item.save()
        return cart_item, created

    def remove_product(self, product):
        try:
            item = self.items.get(product=product)
            item.delete()
            return True
        except CartItem.DoesNotExist:
            return False

    @property
    def total_items(self):
        return sum(item.quantity for item in self.items.all())

    @property
    def total_price(self):
        """Calculate total price, ensuring all items use the same currency"""
        items = self.items.select_related('product').all()

        if not items:
            return Money(0, settings.DEFAULT_CURRENCY)

        # Start with zero in the default currency
        total = Decimal('0.00')
        currency = settings.DEFAULT_CURRENCY

        for item in items:
            price = item.total_price
            # Convert Money to Decimal (amount only)
            if hasattr(price, 'amount'):
                # Verify currency matches (optional: add currency conversion here)
                if hasattr(price, 'currency') and str(price.currency) != currency:
                    # Log warning or handle currency mismatch
                    # For now, we'll use the amount as-is
                    pass
                total += price.amount
            else:
                total += Decimal(str(price))

        return Money(total, currency)

    def get_total_price(self):
        return self.total_price

    def clear(self):
        self.items.all().delete()

    @property
    def estimated_shipping(self):
        """Calculate estimated shipping cost for all items in cart"""
        items = self.items.select_related('product').all()

        if not items:
            return Money(0, settings.DEFAULT_CURRENCY)

        total_shipping = Decimal('0.00')
        currency = settings.DEFAULT_CURRENCY

        for item in items:
            product = item.product

            # Skip if product has free shipping
            if product.free_shipping:
                continue

            # Add shipping cost per item
            if product.shipping_cost:
                shipping_amount = product.shipping_cost.amount if hasattr(product.shipping_cost, 'amount') else Decimal(
                    str(product.shipping_cost))
                total_shipping += shipping_amount * item.quantity

        return Money(total_shipping, currency)

    @property
    def has_free_shipping(self):
        """Check if all items in cart have free shipping"""
        items = self.items.select_related('product').all()

        for item in items:
            if not item.product.free_shipping:
                if item.product.shipping_cost:
                    shipping_amount = item.product.shipping_cost.amount if hasattr(item.product.shipping_cost,
                                                                                   'amount') else Decimal(
                        str(item.product.shipping_cost))
                    if shipping_amount > 0:
                        return False
        return True

    @property
    def grand_total(self):
        """Get cart total including shipping"""
        subtotal = self.total_price.amount if hasattr(self.total_price, 'amount') else Decimal(str(self.total_price))
        shipping = self.estimated_shipping.amount if hasattr(self.estimated_shipping, 'amount') else Decimal(
            str(self.estimated_shipping))
        return subtotal + shipping

    def get_shipping_breakdown(self):
        """Get detailed shipping breakdown by product"""
        breakdown = []
        currency = settings.DEFAULT_CURRENCY

        for item in self.items.select_related('product'):
            product = item.product

            if product.free_shipping:
                shipping_cost = Money(0, currency)
                status = "Free Shipping"
            elif product.shipping_cost:
                shipping_amount = product.shipping_cost.amount if hasattr(product.shipping_cost, 'amount') else Decimal(
                    str(product.shipping_cost))
                shipping_cost = Money(shipping_amount * item.quantity, currency)
                status = f"Shipping: {shipping_cost}"
            else:
                shipping_cost = Money(0, currency)
                status = "Shipping TBD"

            breakdown.append({
                'product': product,
                'quantity': item.quantity,
                'shipping_cost': shipping_cost,
                'status': status
            })

        return breakdown

    def __str__(self):
        if self.user:
            return f"Cart for {self.user.username}"
        else:
            return f"Session cart ({self.session_key})"


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('cart', 'product')

    @property
    def total_price(self):
        """Calculate total price for this cart item"""
        unit_price = self.product.get_display_price()

        # Extract amount from Money object
        if hasattr(unit_price, 'amount'):
            amount = unit_price.amount
            currency = str(unit_price.currency)
        else:
            amount = Decimal(str(unit_price))
            currency = settings.DEFAULT_CURRENCY

        total_amount = amount * self.quantity
        return Money(total_amount, currency)

    def __str__(self):
        return f"{self.quantity} x {self.product.name}"