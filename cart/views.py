from django.db import transaction
from django.dispatch.dispatcher import logger
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from store.models import Product
from .models import Cart, CartItem
from .forms import CartAddProductForm


@login_required
def cart_detail(request):
    cart, created = Cart.objects.get_or_create(user=request.user)
    cart_has_stock_issues = False

    # Check for stock issues
    for item in cart.items.all():
        if item.quantity > item.product.stock:
            cart_has_stock_issues = True
            # Auto-correct quantity to max available
            item.quantity = item.product.stock
            item.save()

    return render(request, 'cart/detail.html', {
        'cart': cart,
        'cart_has_stock_issues': cart_has_stock_issues
    })


@login_required
def cart_add(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    form = CartAddProductForm(request.POST or None)

    response_data = {
        'success': False,
        'message': '',
        'cart_total_items': 0
    }

    if request.method == 'POST' and form.is_valid():
        quantity = form.cleaned_data['quantity']
        update_quantity = form.cleaned_data.get('update', False)

        try:
            with transaction.atomic():
                cart, created = Cart.objects.select_for_update().get_or_create(user=request.user)

                # Check if product is already in cart
                cart_item_exists = cart.items.filter(product=product).exists()

                # Prevent adding duplicate items
                if cart_item_exists and not update_quantity:
                    response_data['success'] = False
                    response_data['message'] = 'Product is already in your cart'
                else:
                    cart.add_product(product, quantity, update_quantity=update_quantity)
                    cart.refresh_from_db()

                    response_data['success'] = True
                    response_data['message'] = 'Product added to cart!'
                    response_data['cart_total_items'] = cart.total_items
                    response_data['is_new_item'] = not cart_item_exists

        except Exception as e:
            logger.error(f"Cart add error: {str(e)}")
            response_data['message'] = 'Server error. Please try again later.'

        # For AJAX requests
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse(response_data)

        return redirect('cart:cart_detail')

    # Handle form errors
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        response_data['message'] = 'Form is invalid'
        return JsonResponse(response_data, status=400)

    return redirect(product.get_absolute_url())


@login_required
def cart_remove(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    cart = get_object_or_404(Cart, user=request.user)

    try:
        item = cart.items.get(product=product)
        item.delete()
    except CartItem.DoesNotExist:
        pass

    return redirect('cart:cart_detail')


@login_required
def cart_clear(request):
    cart = get_object_or_404(Cart, user=request.user)
    cart.clear()
    return redirect('cart:cart_detail')


@login_required
def cart_update(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    cart = get_object_or_404(Cart, user=request.user)

    if request.method == 'POST':
        form = CartAddProductForm(request.POST)
        if form.is_valid():
            quantity = form.cleaned_data['quantity']

            try:
                item = cart.items.get(product=product)
                item.quantity = quantity

                # Ensure quantity doesn't exceed stock
                if item.quantity > product.stock:
                    item.quantity = product.stock

                item.save()
            except CartItem.DoesNotExist:
                pass

    return redirect('cart:cart_detail')