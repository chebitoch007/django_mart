from django.contrib.auth import get_user_model
from cart.models import Cart
import logging

logger = logging.getLogger(__name__)

def clear_user_cart(user):
    """Clear the user's cart after successful payment"""
    try:
        if user and user.is_authenticated:
            user_carts = Cart.objects.filter(user=user)
            if user_carts.exists():
                cart = user_carts.first()
                item_count = cart.items.count()
                cart.clear()
                logger.info(f"Cleared cart for user {user.id}: {item_count} items removed")
                return True
        return False
    except Exception as e:
        logger.error(f"Error clearing cart: {str(e)}")
        return False