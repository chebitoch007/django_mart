from .utils import get_cart

def cart(request):
    try:
        cart_obj = get_cart(request)
        return {
            'cart': cart_obj,
            'cart_total_items': cart_obj.total_items,
            'cart_total_price': cart_obj.total_price,
            'cart_has_items': cart_obj.total_items > 0
        }
    except Exception:
        return {
            'cart': None,
            'cart_total_items': 0,
            'cart_total_price': 0,
            'cart_has_items': False
        }