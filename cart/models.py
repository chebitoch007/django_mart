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
        cart_item, created = self.items.get_or_create(product=product)

        if update_quantity:
            cart_item.quantity = quantity
        elif created:
            cart_item.quantity = quantity
        else:
            return cart_item, False  # Not created

        # Ensure quantity doesn't exceed stock
        if cart_item.quantity > product.stock:
            cart_item.quantity = product.stock

        cart_item.save()
        return cart_item, created

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