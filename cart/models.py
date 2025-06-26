from django.db import models
from django.contrib.auth import get_user_model
from store.models import Product

User = get_user_model()


class Cart(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='user_cart')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def add_product(self, product, quantity=1, update_quantity=False):
        cart_item, created = self.items.get_or_create(product=product)

        if update_quantity:
            cart_item.quantity = quantity
        else:
            # Only add if the product is not already in cart
            if created:
                cart_item.quantity = quantity
            else:
                # Don't increment quantity if already in cart
                return cart_item, False  # Return created flag

        # Ensure quantity doesn't exceed available stock
        if cart_item.quantity > product.stock:
            cart_item.quantity = product.stock

        cart_item.save()
        return cart_item, created


    @property
    def total_price(self):
        return sum(item.total_price for item in self.items.all())

    @property
    def total_items(self):
        return sum(item.quantity for item in self.items.all())

    def clear(self):
        self.items.all().delete()


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('cart', 'product')  # Prevent duplicate products

    @property
    def total_price(self):
        return self.product.get_display_price() * self.quantity