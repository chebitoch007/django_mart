# cart/models.py

from django.db import models
from django.contrib.auth import get_user_model
from django.db.models import Q
from store.models import Product
from decimal import Decimal
from djmoney.money import Money
from django.conf import settings
from core.utils import get_exchange_rate
import logging

User = get_user_model()
logger = logging.getLogger(__name__)


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

    def get_total_price_in_currency(self, currency):
        """
        ✅ NEW: Calculate total price in a specific currency
        This ensures all cart calculations use the user's selected currency
        """
        items = self.items.select_related('product').all()

        if not items:
            return Money(0, currency)

        total = Decimal('0.00')

        for item in items:
            # Get product price
            product_price = item.product.get_display_price()
            price_currency = str(product_price.currency)
            price_amount = product_price.amount

            # Convert to target currency if needed
            if price_currency != currency:
                try:
                    rate = get_exchange_rate(price_currency, currency)
                    price_amount = price_amount * rate
                except Exception as e:
                    logger.error(f"Currency conversion error in cart: {e}")
                    # Continue with original amount if conversion fails
                    pass

            total += price_amount * item.quantity

        return Money(total, currency)

    @property
    def total_price(self):
        """
        Calculate total price in default currency.
        ⚠️ For display, use get_total_price_in_currency(user_currency) instead
        """
        return self.get_total_price_in_currency(settings.DEFAULT_CURRENCY)

    def get_total_price(self):
        """Legacy method for compatibility"""
        return self.total_price

    def get_estimated_shipping_in_currency(self, currency):
        """
        ✅ NEW: Calculate estimated shipping cost in a specific currency
        """
        items = self.items.select_related('product').all()

        if not items:
            return Money(0, currency)

        total_shipping = Decimal('0.00')

        for item in items:
            product = item.product

            # Skip if product has free shipping
            if product.free_shipping:
                continue

            # Get shipping cost
            if product.shipping_cost:
                shipping_currency = str(product.shipping_cost.currency)
                shipping_amount = product.shipping_cost.amount

                # Convert to target currency if needed
                if shipping_currency != currency:
                    try:
                        rate = get_exchange_rate(shipping_currency, currency)
                        shipping_amount = shipping_amount * rate
                    except Exception as e:
                        logger.error(f"Shipping conversion error in cart: {e}")
                        pass

                total_shipping += shipping_amount * item.quantity

        return Money(total_shipping, currency)

    @property
    def estimated_shipping(self):
        """
        Calculate estimated shipping in default currency.
        ⚠️ For display, use get_estimated_shipping_in_currency(user_currency)
        """
        return self.get_estimated_shipping_in_currency(settings.DEFAULT_CURRENCY)

    @property
    def has_free_shipping(self):
        """Check if all items in cart have free shipping"""
        items = self.items.select_related('product').all()

        for item in items:
            if not item.product.free_shipping:
                if item.product.shipping_cost and item.product.shipping_cost.amount > 0:
                    return False
        return True

    def get_grand_total_in_currency(self, currency):
        """
        ✅ NEW: Get cart total including shipping in specific currency
        """
        subtotal = self.get_total_price_in_currency(currency)
        shipping = self.get_estimated_shipping_in_currency(currency)
        return Money(subtotal.amount + shipping.amount, currency)

    @property
    def grand_total(self):
        """
        Get cart total including shipping in default currency.
        ⚠️ For display, use get_grand_total_in_currency(user_currency)
        """
        return self.get_grand_total_in_currency(settings.DEFAULT_CURRENCY)

    def get_shipping_breakdown(self, currency=None):
        """
        ✅ UPDATED: Get detailed shipping breakdown by product in specified currency
        """
        if currency is None:
            currency = settings.DEFAULT_CURRENCY

        breakdown = []

        for item in self.items.select_related('product'):
            product = item.product

            if product.free_shipping:
                shipping_cost = Money(0, currency)
                status = "Free Shipping"
            elif product.shipping_cost:
                shipping_currency = str(product.shipping_cost.currency)
                shipping_amount = product.shipping_cost.amount

                # Convert to target currency if needed
                if shipping_currency != currency:
                    try:
                        rate = get_exchange_rate(shipping_currency, currency)
                        shipping_amount = shipping_amount * rate
                    except Exception as e:
                        logger.error(f"Shipping breakdown conversion error: {e}")

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

    def clear(self):
        """Removes all items from the cart."""
        self.items.all().delete()
        self.save()


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('cart', 'product')

    def get_total_price_in_currency(self, currency):
        """
        ✅ NEW: Calculate item total in specific currency
        """
        unit_price = self.product.get_display_price()
        price_currency = str(unit_price.currency)
        amount = unit_price.amount

        # Convert to target currency if needed
        if price_currency != currency:
            try:
                rate = get_exchange_rate(price_currency, currency)
                amount = amount * rate
            except Exception as e:
                logger.error(f"Item price conversion error: {e}")

        return Money(amount * self.quantity, currency)

    @property
    def total_price(self):
        """
        Calculate total price for this cart item in product's currency.
        ⚠️ For display, use get_total_price_in_currency(user_currency)
        """
        unit_price = self.product.get_display_price()
        amount = unit_price.amount if hasattr(unit_price, 'amount') else Decimal(str(unit_price))
        currency = str(unit_price.currency) if hasattr(unit_price, 'currency') else settings.DEFAULT_CURRENCY

        total_amount = amount * self.quantity
        return Money(total_amount, currency)

    def __str__(self):
        return f"{self.quantity} x {self.product.name}"