from django.shortcuts import render, redirect, get_object_or_404
from .cart import Cart
from django.contrib.auth.decorators import login_required
from store.models import Product
from .models import Cart
from .forms import CartAddProductForm



@login_required
def cart_detail(request):
    cart = get_object_or_404(Cart, user=request.user)
    return render(request, 'cart/detail.html', {'cart': cart})


@login_required
def cart_add(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    cart, created = Cart.objects.get_or_create(user=request.user)
    form = CartAddProductForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        quantity = form.cleaned_data['quantity']
        cart.add_product(product, quantity)
        return redirect('cart:detail')

    # Handle GET requests or invalid forms
    return redirect(product.get_absolute_url())


@login_required
def cart_remove(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    cart = get_object_or_404(Cart, user=request.user)
    cart.remove_product(product)
    return redirect('cart:detail')


@login_required
def cart_clear(request):
    cart = get_object_or_404(Cart, user=request.user)
    cart.clear()
    return redirect('cart:detail')


@login_required
def cart_update(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    cart = get_object_or_404(Cart, user=request.user)
    item = get_object_or_404(cart.items, product=product)

    if request.method == 'POST':
        form = CartAddProductForm(request.POST, instance=item)
        if form.is_valid():
            form.save()
    return redirect('cart:detail')


