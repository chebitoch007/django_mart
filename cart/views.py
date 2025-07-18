from django.db import transaction
from django.dispatch.dispatcher import logger
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required

from orders.models import Order
from store.models import Product
from .models import Cart, CartItem
from .forms import CartAddProductForm
from .utils import get_cart


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
        # Only proceed if cart has items
        if not cart.items.exists():
            return redirect('cart:cart_detail')

        # Create order only when proceeding to checkout
        order = Order.objects.create(
            user=request.user if request.user.is_authenticated else None,
            total=cart.total_price,
        )
        request.session['order_id'] = order.id
        return redirect('orders:checkout')

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
        update_quantity = form.cleaned_data.get('update', False)

        try:
            with transaction.atomic():
                cart = get_cart(request)
                cart_item_exists = cart.items.filter(product=product).exists()

                if cart_item_exists and not update_quantity:
                    response_data['message'] = 'Product is already in your cart'
                else:
                    cart.add_product(product, quantity, update_quantity=update_quantity)
                    response_data['success'] = True
                    response_data['message'] = 'Product added to cart!'
                    response_data['cart_total_items'] = cart.total_items
                    response_data['is_new_item'] = not cart_item_exists

        except Exception as e:
            logger.error(f"Cart add error: {str(e)}")
            response_data['message'] = 'Server error. Please try again later.'

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse(response_data)
        return redirect('cart:cart_detail')

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        response_data['message'] = 'Form is invalid'
        return JsonResponse(response_data, status=400)
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
            'cart_total_price': cart.total_price
        }
    except CartItem.DoesNotExist:
        pass

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse(response_data)
    return redirect('cart:cart_detail')


def cart_clear(request):
    cart = get_cart(request)
    cart.clear()
    return redirect('cart:cart_detail')


def cart_update(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    cart = get_cart(request)
    response_data = {'success': False, 'message': 'Item not in cart'}

    if request.method == 'POST':
        form = CartAddProductForm(request.POST)
        if form.is_valid():
            quantity = form.cleaned_data['quantity']
            exceeded_stock = False

            try:
                item = cart.items.get(product=product)
                item.quantity = quantity

                if quantity > product.stock:
                    item.quantity = product.stock
                    exceeded_stock = True
                elif quantity < 1:
                    item.quantity = 1

                item.save()
                response_data = {
                    'success': True,
                    'item': {
                        'item_total': item.total_price,
                        'quantity': item.quantity,
                        'product_stock': product.stock
                    },
                    'cart_total_items': cart.total_items,
                    'cart_total_price': cart.total_price,
                    'message': 'Quantity adjusted due to stock limits' if exceeded_stock else ''
                }
            except CartItem.DoesNotExist:
                pass

            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse(response_data)
    return redirect('cart:cart_detail')


# FIXED: Removed trailing comma and extra text
def cart_total(request):
    cart = get_cart(request)
    return JsonResponse({
        'success': True,
        'cart_total_items': cart.total_items
    })