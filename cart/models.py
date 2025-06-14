from django.db import models
from django.contrib.auth import get_user_model
from store.models import Product

User = get_user_model()


class Cart(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def add_product(self, product, quantity=1, update_quantity=False):
        """
        Add a product to the cart or update its quantity.
        - `update_quantity=True` will set the quantity instead of adding.
        """
        cart_item, created = self.items.get_or_create(product=product)

        if created:
            cart_item.quantity = quantity
        else:
            if update_quantity:
                cart_item.quantity = quantity
            else:
                cart_item.quantity += quantity

        cart_item.save()
        self.save()  # Update the cart's updated_at timestamp

    @property
    def total_price(self):
        return sum(item.total_price for item in self.items.all())

    @property
    def total_items(self):
        return self.items.count()


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    added_at = models.DateTimeField(auto_now_add=True)

    @property
    def total_price(self):
        return self.product.price * self.quantity