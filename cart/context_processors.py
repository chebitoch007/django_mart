# cart/context_processors.py
from .utils import get_cart

def cart_context(request):
    try:
        cart_obj = get_cart(request)
        if cart_obj and hasattr(cart_obj, 'total_items'):
            return {
                'cart': cart_obj,
                'cart_total_items': cart_obj.total_items,
                'cart_total_price': cart_obj.total_price,
                'cart_has_items': cart_obj.total_items > 0
            }
        else:
            return {
                'cart': None,
                'cart_total_items': 0,
                'cart_total_price': 0,
                'cart_has_items': False
            }
    except Exception:
        return {
            'cart': None,
            'cart_total_items': 0,
            'cart_total_price': 0,
            'cart_has_items': False
        }