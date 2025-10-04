
from django.dispatch import receiver
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.contrib.auth import get_user_model
from core.utils import logger
from .models import Cart
from .utils import merge_carts

User = get_user_model()


@receiver(user_logged_in)
def merge_carts_on_login(sender, request, user, **kwargs):
    """
    Merge session cart into user cart when user logs in
    """
    session_cart_id = request.session.get('cart_id')

    if session_cart_id:
        try:
            # Get both carts
            session_cart = Cart.objects.get(id=session_cart_id, user__isnull=True)
            user_cart, created = Cart.objects.get_or_create(user=user)

            # Merge session cart into user cart
            merge_carts(user_cart, session_cart)

            # Delete session cart and clean up session
            session_cart.delete()
            if 'cart_id' in request.session:
                del request.session['cart_id']

        except Cart.DoesNotExist:
            # Session cart doesn't exist, clean up
            if 'cart_id' in request.session:
                del request.session['cart_id']


@receiver(user_logged_out)
def preserve_cart_on_logout(sender, request, user, **kwargs):
    """
    Preserve user cart when logging out by converting to session cart
    """
    try:
        # Get the user's cart
        user_cart = Cart.objects.get(user=user)

        # Check if there's already a session cart
        session_cart_id = request.session.get('cart_id')

        if session_cart_id:
            try:
                # Get the existing session cart
                session_cart = Cart.objects.get(id=session_cart_id, user__isnull=True)
                # Merge user cart into session cart
                merge_carts(session_cart, user_cart)
                # Delete the user cart
                user_cart.delete()
            except Cart.DoesNotExist:
                # Session cart doesn't exist, convert user cart to session cart
                user_cart.user = None
                user_cart.session_key = request.session.session_key
                user_cart.save()
                request.session['cart_id'] = user_cart.id
        else:
            # No session cart, convert user cart to session cart
            user_cart.user = None
            user_cart.session_key = request.session.session_key
            user_cart.save()
            request.session['cart_id'] = user_cart.id

    except Cart.DoesNotExist:
        # No user cart, nothing to preserve
        pass
    except Exception as e:
        # Log any errors but don't break the logout process
        logger.error(f"Error preserving cart on logout: {str(e)}")