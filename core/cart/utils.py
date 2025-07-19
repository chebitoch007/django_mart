from .models import Cart


def get_cart(request):
    # Create session if needed
    if not request.session.session_key:
        request.session.create()

    session_key = request.session.session_key

    if request.user.is_authenticated:
        # Get or create user cart
        cart, created = Cart.objects.get_or_create(user=request.user)

        # Migrate session cart if exists
        if 'cart_id' in request.session:
            try:
                session_cart = Cart.objects.get(
                    id=request.session['cart_id'],
                    user__isnull=True
                )
                # Transfer items
                for item in session_cart.items.all():
                    # Check for existing product in user cart
                    existing_item = cart.items.filter(product=item.product).first()

                    if existing_item:
                        # Update quantity without exceeding stock
                        new_quantity = min(
                            existing_item.quantity + item.quantity,
                            item.product.stock
                        )
                        existing_item.quantity = new_quantity
                        existing_item.save()
                    else:
                        # Create new item
                        cart.items.create(
                            product=item.product,
                            quantity=min(item.quantity, item.product.stock)
                        )

                # Delete session cart
                session_cart.delete()
                del request.session['cart_id']
            except Cart.DoesNotExist:
                del request.session['cart_id']

        return cart
    else:
        # Get or create session cart
        cart_id = request.session.get('cart_id')

        if cart_id:
            try:
                return Cart.objects.get(id=cart_id, user__isnull=True)
            except Cart.DoesNotExist:
                del request.session['cart_id']

        # Create new session cart
        cart = Cart.objects.create(session_key=session_key)
        request.session['cart_id'] = cart.id
        return cart