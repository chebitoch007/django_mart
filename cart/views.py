import json

from django.views.decorators.http import require_POST
from django.db import transaction, IntegrityError
from django.dispatch.dispatcher import logger
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from orders.models import Order
from store.models import Product
from .models import CartItem
from .forms import CartAddProductForm
from .utils import get_cart, merge_carts


def cart_detail(request):
    cart = get_cart(request)
    cart_has_stock_issues = False

    # Check stock availability
    for item in cart.items.all():
        if item.quantity > item.product.stock:
            cart_has_stock_issues = True
            item.quantity = item.product.stock
            item.save()

    # Handle checkout request
    if request.method == 'POST' and 'checkout' in request.POST:
        if not cart.items.exists():
            return redirect('cart:cart_detail')

        try:
            # Create order for authenticated users or guests
            order = Order.objects.create(
                user=request.user if request.user.is_authenticated else None,
                total=cart.total_price,
                # Add default values for required fields
                first_name='Guest' if not request.user.is_authenticated else request.user.first_name,
                last_name='User' if not request.user.is_authenticated else request.user.last_name,
                email=request.user.email if request.user.is_authenticated else 'guest@example.com',
                address='To be provided' if not request.user.is_authenticated else '',
                postal_code='00000',
                city='N/A',
                country='Kenya'
            )
            request.session['order_id'] = order.id
            return redirect('orders:checkout')
        except IntegrityError as e:
            # Handle database errors gracefully
            logger.error(f"Order creation failed: {str(e)}")
            return render(request, 'cart/detail.html', {
                'cart': cart,
                'cart_has_stock_issues': cart_has_stock_issues,
                'error_message': 'Could not process your order. Please try again or contact support.'
            })

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
                    # Use update_quantity=True for new items or when explicitly updating
                    cart.add_product(product, quantity, update_quantity=update_quantity or not cart_item_exists)

                    response_data = {
                        'success': True,
                        'message': f'{product.name} added to cart',
                        'cart_total_items': cart.total_items,
                        'is_new_item': not cart_item_exists,
                        # Add HX-Trigger header for HTMX
                        'HX-Trigger': json.dumps({
                            'cartUpdated': {
                                'cart_total_items': cart.total_items
                            }
                        })
                    }

        except Exception as e:
            logger.error(f"Cart add error: {str(e)}")
            response_data['message'] = 'Server error. Please try again later.'

        # HTMX or AJAX response
        if request.headers.get('HX-Request') or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse(response_data)

        return redirect('cart:cart_detail')

    # Invalid form handling
    if request.headers.get('HX-Request') or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': False,
            'message': 'Invalid quantity or request data.'
        }, status=400)

    return redirect(product.get_absolute_url())



def cart_remove(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    cart = get_cart(request)
    response_data = {'success': False, 'message': 'Item not in cart'}

    try:
        item = cart.items.get(product=product)
        item.delete()
        response_data = {
            'success': True,
            'cart_total_items': cart.total_items,
            'cart_total_price': cart.total_price,
            # Add HX-Trigger header for HTMX
            'HX-Trigger': json.dumps({
                'cartUpdated': {
                    'cart_total_items': cart.total_items
                }
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
            'HX-Trigger': json.dumps({
                'cartUpdated': {
                    'cart_total_items': 0
                }
            })
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
        # Ensure quantity doesn't exceed stock
        if quantity > product.stock:
            quantity = product.stock
            exceeded_stock = True

        if quantity <= 0:
            cart.items.remove(item)
            removed_item = True
            response_data = {
                'success': True,
                'cart_total_price': cart.total_price,
                'cart_total_items': cart.total_items,
                'message': 'Item removed from cart',
                # Add HX-Trigger header for HTMX
                'HX-Trigger': json.dumps({
                    'cartUpdated': {
                        'cart_total_items': cart.total_items
                    }
                })
            }
        else:
            item.quantity = quantity
            item.save()
            response_data = {
                'success': True,
                'item_total': item.total_price,
                'cart_total_price': cart.total_price,
                'cart_total_items': cart.total_items,
                'item_quantity': quantity,
                'product_stock': product.stock,
                'message': 'Quantity adjusted due to stock limits' if exceeded_stock else 'Quantity updated',
                # Add HX-Trigger header for HTMX
                'HX-Trigger': json.dumps({
                    'cartUpdated': {
                        'cart_total_items': cart.total_items
                    }
                })
            }

    except CartItem.DoesNotExist:
        response_data['message'] = 'Item not found in cart'

    return JsonResponse(response_data)


# FIXED: Removed trailing comma and extra text
def cart_total(request):
    cart = get_cart(request)
    return JsonResponse({
        'success': True,
        'cart_total_items': cart.total_items
    })