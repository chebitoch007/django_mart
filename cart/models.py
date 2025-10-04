from django.db import models
from django.contrib.auth import get_user_model
from store.models import Product

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
                fields=['user', 'session_key'],
                name='unique_user_or_session'
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