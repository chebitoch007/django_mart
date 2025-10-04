from .models import Cart, CartItem


def get_cart(request):
    # Create session if needed
    if not request.session.session_key:
        request.session.create()

    session_key = request.session.session_key

    if request.user.is_authenticated:
        # Get or create user cart
        cart, created = Cart.objects.get_or_create(user=request.user)

        # Check if there's a session cart to merge
        session_cart_id = request.session.get('cart_id')
        if session_cart_id:
            try:
                session_cart = Cart.objects.get(
                    id=session_cart_id,
                    user__isnull=True
                )
                # Merge session cart into user cart
                merge_carts(cart, session_cart)

                # Delete session cart and remove from session
                session_cart.delete()
                del request.session['cart_id']
            except Cart.DoesNotExist:
                # Session cart doesn't exist, clean up session
                if 'cart_id' in request.session:
                    del request.session['cart_id']

        return cart
    else:
        # Get or create session cart
        cart_id = request.session.get('cart_id')

        if cart_id:
            try:
                return Cart.objects.get(id=cart_id, user__isnull=True)
            except Cart.DoesNotExist:
                # Cart doesn't exist, clean up session
                del request.session['cart_id']

        # Create new session cart
        cart = Cart.objects.create(session_key=session_key)
        request.session['cart_id'] = cart.id
        return cart


def merge_carts(target_cart, source_cart):
    """
    Merge items from source cart into target cart
    """
    for source_item in source_cart.items.all():
        # Check if product already exists in target cart
        try:
            target_item = target_cart.items.get(product=source_item.product)
            # Update quantity without exceeding stock
            new_quantity = min(
                target_item.quantity + source_item.quantity,
                source_item.product.stock
            )
            target_item.quantity = new_quantity
            target_item.save()
        except CartItem.DoesNotExist:
            # Create new item in target cart
            target_cart.items.create(
                product=source_item.product,
                quantity=min(source_item.quantity, source_item.product.stock)
            )