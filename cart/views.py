# cart/views.py - PERFECT CURRENCY HANDLING

import json
from django.db import transaction
from django.dispatch.dispatcher import logger
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from djmoney.money import Money
from store.models import Product
from .forms import CartAddProductForm
from .models import CartItem
from .utils import get_cart
from django.conf import settings
from decimal import Decimal


def format_money_for_display(money_obj, request):
    """
    Format Money object for display with user's selected currency.
    Returns formatted string like "KES 1,234.56" or "$1,234.56"
    """
    if not money_obj:
        user_currency = request.session.get('user_currency', settings.DEFAULT_CURRENCY)
        return f"{user_currency} 0.00"

    # Get user's selected currency
    user_currency = request.session.get('user_currency', settings.DEFAULT_CURRENCY)

    # Extract source currency and amount
    if hasattr(money_obj, 'currency'):
        source_currency = str(money_obj.currency)
        amount = money_obj.amount
    else:
        source_currency = settings.DEFAULT_CURRENCY
        amount = Decimal(str(money_obj))

    # Convert if needed
    if source_currency != user_currency:
        try:
            from core.utils import get_exchange_rate
            rate = get_exchange_rate(source_currency, user_currency)
            amount = Decimal(str(amount)) * rate
        except Exception as e:
            logger.error(f"Currency conversion error: {e}")
            # Fall back to original
            user_currency = source_currency

    # Format with currency configuration
    format_config = settings.CURRENCY_FORMATS.get(user_currency, {})
    decimal_places = format_config.get('decimal_places', 2)
    symbol = settings.CURRENCY_SYMBOLS.get(user_currency, user_currency)

    # Format the number with commas
    formatted_amount = f"{amount:,.{decimal_places}f}"

    # Return with symbol/code
    symbol_before = ['$', '£', '€', '¥'].count(symbol) > 0
    if symbol_before:
        return f"{symbol}{formatted_amount}"
    else:
        return f"{user_currency} {formatted_amount}"


def cart_detail(request):
    cart = get_cart(request)
    cart_has_stock_issues = False

    # Check stock availability
    for item in cart.items.all():
        if item.quantity > item.product.stock:
            cart_has_stock_issues = True
            item.quantity = item.product.stock
            item.save()

    if request.method == 'POST' and 'checkout' in request.POST:
        if not cart.items.exists():
            return redirect('cart:cart_detail')
        return redirect('orders:create_order')

    return render(request, 'cart/detail.html', {
        'cart': cart,
        'cart_has_stock_issues': cart_has_stock_issues
    })


def cart_add(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    form = CartAddProductForm(request.POST or None)
    response_data = {'success': False, 'message': '', 'cart_total_items': 0}

    if request.method == 'POST' and form.is_valid():
        quantity = form.cleaned_data['quantity']
        update_quantity = form.cleaned_data.get('update') or form.cleaned_data.get('override') or False

        try:
            with transaction.atomic():
                cart = get_cart(request)
                cart_item_exists = cart.items.filter(product=product).exists()

                if cart_item_exists and not update_quantity:
                    response_data['message'] = 'Product is already in your cart'
                else:
                    cart.add_product(product, quantity, update_quantity=update_quantity or not cart_item_exists)
                    response_data = {
                        'success': True,
                        'message': f'{product.name} added to cart',
                        'cart_total_items': cart.total_items,
                        'is_new_item': not cart_item_exists,
                        'HX-Trigger': json.dumps({
                            'cartUpdated': {'cart_total_items': cart.total_items}
                        })
                    }

        except Exception as e:
            logger.error(f"Cart add error: {str(e)}")
            response_data['message'] = 'Server error. Please try again later.'

        if request.headers.get('HX-Request') or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse(response_data)
        return redirect('cart:cart_detail')

    if request.headers.get('HX-Request') or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': False, 'message': 'Invalid quantity or request data.'}, status=400)

    return redirect(product.get_absolute_url())


def cart_remove(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    cart = get_cart(request)
    response_data = {'success': False, 'message': 'Item not in cart'}

    try:
        item = cart.items.get(product=product)
        item.delete()

        # Return formatted prices
        response_data = {
            'success': True,
            'cart_total_items': cart.total_items,
            'cart_total_price': format_money_for_display(cart.total_price, request),
            'HX-Trigger': json.dumps({
                'cartUpdated': {'cart_total_items': cart.total_items}
            })
        }
    except CartItem.DoesNotExist:
        pass

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse(response_data)
    return redirect('cart:cart_detail')


def cart_clear(request):
    cart = get_cart(request)
    cart.clear()

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'cart_total_items': 0,
            'message': 'Cart cleared successfully',
            'HX-Trigger': json.dumps({'cartUpdated': {'cart_total_items': 0}})
        })
    return redirect('cart:cart_detail')


@require_POST
def cart_update(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    cart = get_cart(request)
    response_data = {'success': False, 'message': 'Item not found in cart'}

    try:
        quantity = int(request.POST.get('quantity', 1))
    except (TypeError, ValueError):
        quantity = 1

    exceeded_stock = False
    removed_item = False

    try:
        item = cart.items.get(product=product)

        if quantity > product.stock:
            quantity = product.stock
            exceeded_stock = True

        if quantity <= 0:
            item.delete()
            removed_item = True
            response_data = {
                'success': True,
                'cart_total_price': format_money_for_display(cart.total_price, request),
                'cart_total_items': cart.total_items,
                'message': 'Item removed from cart',
                'HX-Trigger': json.dumps({'cartUpdated': {'cart_total_items': cart.total_items}})
            }
        else:
            item.quantity = quantity
            item.save()

            # Return formatted prices
            response_data = {
                'success': True,
                'item_total': format_money_for_display(item.total_price, request),
                'cart_total_price': format_money_for_display(cart.total_price, request),
                'cart_total_items': cart.total_items,
                'item_quantity': quantity,
                'product_stock': product.stock,
                'message': 'Quantity adjusted due to stock limits' if exceeded_stock else 'Quantity updated',
                'HX-Trigger': json.dumps({'cartUpdated': {'cart_total_items': cart.total_items}})
            }

    except CartItem.DoesNotExist:
        response_data['message'] = 'Item not found in cart'

    return JsonResponse(response_data)


def cart_total(request):
    cart = get_cart(request)
    return JsonResponse({
        'success': True,
        'cart_total_items': cart.total_items,
        'cart_total_price': format_money_for_display(cart.total_price, request)
    })