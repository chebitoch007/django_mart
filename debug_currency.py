from orders.models import Order, OrderItem
from cart.models import Cart, CartItem
from payment.models import Payment
from django.contrib.auth import get_user_model
from djmoney.money import Money

User = get_user_model()

def debug_order_pricing(order_id):
    """Debug pricing for a specific order"""
    print(f"\n{'='*60}")
    print(f"DEBUGGING ORDER #{order_id}")
    print(f"{'='*60}\n")

    try:
        order = Order.objects.prefetch_related('items__product').get(id=order_id)

        print(f"Order Status: {order.status}")
        print(f"Order Currency: {order.total.currency.code}")
        print(f"Order Total Amount: {order.total.amount}")
        print(f"Order Total (formatted): {order.total}")
        print(f"\n{'─'*60}\n")

        print("ORDER ITEMS:")
        print(f"{'Product':<30} {'Qty':<5} {'Price':<15} {'Total':<15}")
        print(f"{'-'*30} {'-'*5} {'-'*15} {'-'*15}")

        calculated_subtotal = Money(0, order.total.currency.code)

        for item in order.items.all():
            item_total = item.total_price
            print(f"{item.product.name[:28]:<30} {item.quantity:<5} {item.price} {item_total}")

            if item.price.currency.code != order.total.currency.code:
                print(f"  ⚠️  WARNING: Item currency ({item.price.currency.code}) "
                      f"!= Order currency ({order.total.currency.code})")

            calculated_subtotal += item_total

        print(f"\n{'─'*60}\n")

        print("VERIFICATION:")
        print(f"Calculated Subtotal: {calculated_subtotal}")
        print(f"Order Subtotal:      {order.subtotal}")
        print(f"Order Shipping:      {order.shipping_cost}")
        print(f"Order Total:         {order.total}")
        print(f"Calculated Total:    {order.subtotal + order.shipping_cost}")

        if calculated_subtotal.amount != order.subtotal.amount:
            print(f"\n❌ MISMATCH: Calculated subtotal doesn't match order subtotal!")
            print(f"   Difference: {calculated_subtotal.amount - order.subtotal.amount}")

        try:
            payment = order.payment
            print(f"\n{'─'*60}\n")
            print("PAYMENT RECORD:")
            print(f"Payment Status:     {payment.status}")
            print(f"Payment Amount:     {payment.amount}")
            print(f"Original Amount:    {payment.original_amount}")
            print(f"Converted Amount:   {payment.converted_amount}")

            if payment.amount != order.total:
                print(f"\n❌ MISMATCH: Payment amount doesn't match order total!")
                print(f"   Difference: {payment.amount.amount - order.total.amount}")

        except Payment.DoesNotExist:
            print(f"\n⚠️  WARNING: No payment record found for this order")

        print(f"\n{'='*60}\n")

    except Order.DoesNotExist:
        print(f"❌ Order #{order_id} not found")


def debug_cart_pricing(user_email):
    """Debug cart pricing for a user"""
    print(f"\n{'='*60}")
    print(f"DEBUGGING CART FOR: {user_email}")
    print(f"{'='*60}\n")

    try:
        user = User.objects.get(email=user_email)
        cart = Cart.objects.get(user=user)

        user_currency = 'EUR'  # Change if needed

        print(f"Cart Items: {cart.items.count()}")
        print(f"User Currency: {user_currency}")
        print(f"\n{'─'*60}\n")

        print("CART ITEMS:")
        print(f"{'Product':<30} {'Qty':<5} {'Price':<15} {'Total':<15}")
        print(f"{'-'*30} {'-'*5} {'-'*15} {'-'*15}")

        for item in cart.items.select_related('product'):
            product_price = item.product.get_display_price()
            item_total = item.get_total_price_in_currency(user_currency)
            print(f"{item.product.name[:28]:<30} {item.quantity:<5} {product_price} {item_total}")

        cart_total = cart.get_total_price_in_currency(user_currency)
        cart_shipping = cart.get_estimated_shipping_in_currency(user_currency)
        cart_grand_total = cart.get_grand_total_in_currency(user_currency)

        print(f"\n{'─'*60}\n")
        print("CART TOTALS:")
        print(f"Subtotal:     {cart_total}")
        print(f"Shipping:     {cart_shipping}")
        print(f"Grand Total:  {cart_grand_total}")

        print(f"\n{'='*60}\n")

    except User.DoesNotExist:
        print(f"❌ User {user_email} not found")
    except Cart.DoesNotExist:
        print(f"❌ No cart found for user {user_email}")
