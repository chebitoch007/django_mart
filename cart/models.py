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
        # ✅ FIXED: Replaced incorrect constraint
        constraints = [
            # Enforce session_key is unique *only* for guest carts (where user is null)
            models.UniqueConstraint(
                fields=['session_key'],
                condition=Q(user__isnull=True),
                name='unique_session_key_if_user_is_null'
            )
        ]

    def add_product(self, product, quantity=1, update_quantity=False):
        # Ensure quantity is positive
        if quantity < 1:
            return None, False

        cart_item, created = self.items.get_or_create(product=product)

        if update_quantity:
            # Set the quantity directly
            cart_item.quantity = quantity
        elif created:
            # For new items, set the quantity
            cart_item.quantity = quantity
        else:
            # For existing items, add to the current quantity
            cart_item.quantity += quantity

        # Ensure quantity doesn't exceed stock
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
        return sum(item.total_price for item in self.items.all())

    def get_total_price(self):
        return self.total_price

    def clear(self):
        self.items.all().delete()

    # --- New Methods Added ---

    @property
    def estimated_shipping(self):
        """Calculate estimated shipping cost for all items in cart"""
        total_shipping = Decimal('0.00')

        for item in self.items.select_related('product'):
            product = item.product

            # Skip if product has free shipping
            if product.free_shipping:
                continue

            # Add shipping cost per item
            if product.shipping_cost:
                total_shipping += product.shipping_cost.amount * item.quantity

        return Money(total_shipping, settings.DEFAULT_CURRENCY)

    @property
    def has_free_shipping(self):
        """Check if all items in cart have free shipping"""
        # Note: This logic assumes free shipping is achieved if *all* items
        # either have .free_shipping=True OR .shipping_cost=0
        # If even one item has a shipping cost > 0, this will return False.
        for item in self.items.select_related('product'):
            if not item.product.free_shipping:
                # If it's not explicitly free, check if it has a cost
                if item.product.shipping_cost and item.product.shipping_cost.amount > 0:
                    return False
        return True

    @property
    def grand_total(self):
        """Get cart total including shipping"""
        subtotal = self.total_price.amount
        shipping = self.estimated_shipping.amount
        return subtotal + shipping

    def get_shipping_breakdown(self):
        """Get detailed shipping breakdown by product"""
        breakdown = []

        for item in self.items.select_related('product'):
            product = item.product

            if product.free_shipping:
                shipping_cost = Money(0, settings.DEFAULT_CURRENCY)
                status = "Free Shipping"
            elif product.shipping_cost:
                shipping_cost = product.shipping_cost * item.quantity
                status = f"Shipping: {shipping_cost}"
            else:
                # Fallback for products with no free_shipping and no shipping_cost
                shipping_cost = Money(0, settings.DEFAULT_CURRENCY)
                status = "Shipping TBD"  # Or "Free" if that's the default

            breakdown.append({
                'product': product,
                'quantity': item.quantity,
                'shipping_cost': shipping_cost,
                'status': status
            })

        return breakdown

    # -------------------------

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
        return self.product.get_display_price() * self.quantity

    def __str__(self):
        return f"{self.quantity} x {self.product.name}"