from django.core.exceptions import ImproperlyConfigured
from .models import Cart


def cart(request):
    """
    Context processor that makes cart available in templates
    """
    try:
        if request.user.is_authenticated:
            cart_obj, created = Cart.objects.get_or_create(user=request.user)
            return {
                'cart': cart_obj,
                'cart_total_items': cart_obj.total_items,
                'cart_total_price': cart_obj.total_price,
                'cart_has_items': cart_obj.total_items > 0
            }
        return {
            'cart': None,
            'cart_total_items': 0,
            'cart_total_price': 0,
            'cart_has_items': False
        }
    except Exception as e:
        raise ImproperlyConfigured(
            f"Error initializing cart context processor: {str(e)}"
        ) from e