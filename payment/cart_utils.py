# payment/cart_utils.py

from django.contrib.auth import get_user_model
from cart.models import Cart
import logging

logger = logging.getLogger(__name__)

def clear_cart_after_payment(order):
    """Clear the user's cart after successful payment with enhanced safety"""
    try:
        user = order.user

        if user and user.is_authenticated:
            # Clear user's cart
            try:

                cart = Cart.objects.get(user=user)
                item_count = cart.items.count()
                cart.clear()
                logger.info(f"Cleared cart for user {user.id}: {item_count} items removed")
                return True
            except Cart.DoesNotExist:
                logger.info(f"No cart found for user {user.id}")
                return True
            except Cart.MultipleObjectsReturned:
                # Handle multiple carts
                carts = Cart.objects.filter(user=user).order_by('-created_at')
                main_cart = carts.first()
                item_count = main_cart.items.count()
                main_cart.clear()

                # Delete duplicate carts
                carts.exclude(id=main_cart.id).delete()
                logger.info(f"Cleared main cart and removed duplicates for user {user.id}")
                return True
        else:
            # For guest users, we need to clear session cart
            # This would require access to the request object
            logger.info("Guest user cart clearing requires session handling")
            return False

    except Exception as e:
        logger.error(f"Error clearing cart after payment: {str(e)}")
        return False