from decimal import Decimal, ROUND_HALF_UP
import logging
from django.conf import settings
import requests
from django.core.cache import cache
from django.db import transaction
from django.http import Http404
from django.views.generic import ListView, DetailView, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, render, redirect
from django.db.models import Prefetch

from cart.cart import Cart
from cart.utils import get_cart
from asai import settings
from payment.models import Payment
#from payment.models import Payment
from .models import Order, OrderItem, CurrencyRate
from django.contrib.auth.decorators import login_required
from payment.utils import get_prioritized_payment_methods
from core.utils import get_exchange_rate
from django import forms
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)


class ShippingForm(forms.Form):
    first_name = forms.CharField(max_length=50)
    last_name = forms.CharField(max_length=50)
    email = forms.EmailField()
    address = forms.CharField(max_length=250)
    postal_code = forms.CharField(max_length=20)
    city = forms.CharField(max_length=100)


@transaction.atomic
def create_order(request):
    cart = get_cart(request)
    if not cart.items.exists():
        return redirect('cart:detail')

    if request.method == 'POST':
        form = ShippingForm(request.POST)
        if form.is_valid():
            shipping_details = form.cleaned_data

            # Create order with shipping details
            order = Order.objects.create(
                user=request.user,
                total_price=cart.total_price,
                currency=request.session.get('currency', 'KES'),
                **shipping_details
            )

            # Create order items
            for cart_item in cart.items.all():
                OrderItem.objects.create(
                    order=order,
                    product=cart_item.product,
                    price=cart_item.product.price,
                    quantity=cart_item.quantity
                )

            # Create payment for the order
            payment = Payment.objects.create(
                order=order,
                amount=cart.total_price,
                currency=request.session.get('currency', 'KES'),
                status='PENDING'
            )

            # Link payment to order
            order.order_payment = payment
            order.save()

            # Clear the cart
            cart.items.all().delete()

            # Redirect to payment checkout
            return redirect('orders:checkout', order_id=order.id)
    else:
        form = ShippingForm()

    return render(request, 'orders/shipping_form.html', {'form': form})


class OrderListView(LoginRequiredMixin, ListView):
    model = Order
    template_name = 'orders/order_list.html'
    context_object_name = 'orders'
    paginate_by = 10

    def get_queryset(self):
        return Order.objects.filter(
            user=self.request.user
        ).select_related('user').prefetch_related(
            Prefetch('items', queryset=OrderItem.objects.select_related('product'))
        ).only(
            'id', 'created', 'status', 'currency', 'user__email'
        ).order_by('-created')


class OrderDetailView(LoginRequiredMixin, DetailView):
    model = Order
    template_name = 'orders/order_detail.html'
    context_object_name = 'order'

    ORDER_FIELDS = [
        'id', 'created', 'status', 'currency', 'payment_method',
        'address', 'postal_code', 'city'
    ]
    USER_FIELDS = ['user__first_name', 'user__last_name', 'user__email']
    ITEM_FIELDS = [
        'items__price', 'items__quantity',
        'items__product__id', 'items__product__name',
        'items__product__price'
    ]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['payment'] = self.object.payment
        return context

    def _build_order_queryset(self):
        """Build optimized queryset for order details."""
        items_queryset = OrderItem.objects.select_related('product')

        return (Order.objects
        .select_related('user')
        .prefetch_related(
            Prefetch('items', queryset=items_queryset)
        )
        .only(
            *self.ORDER_FIELDS,
            *self.USER_FIELDS,
            *self.ITEM_FIELDS
        )
        .filter(
            pk=self.kwargs['pk'],
            user=self.request.user
        ))

def get_object(self):
    try:
        return get_object_or_404(
            self._build_order_queryset(),
            pk=self.kwargs.get('pk')
        )
    except (ValueError, KeyError):
        raise Http404("Invalid order ID")



@login_required
def order_history(request):
    orders = Order.objects.filter(user=request.user).order_by('-created')
    return render(request, 'orders/history.html', {'orders': orders})


class OrderSuccessView(TemplateView):
    template_name = 'orders/success.html'


class CheckoutView(TemplateView):
    template_name = 'orders/checkout.html'

    def get(self, request, *args, **kwargs):
        # If we have an order ID in session, use it
        order_id = request.session.get('order_id')
        if order_id:
            try:
                order = Order.objects.get(id=order_id)
                return render(request, self.template_name, self.get_context_data(order=order))
            except Order.DoesNotExist:
                # Fall through to create new order
                pass

        # If no order exists, try to create one from cart
        cart = get_cart(request)
        if cart.items.exists():
            order = Order.objects.create(
                user=request.user if request.user.is_authenticated else None,
                total=cart.total_price,
            )
            request.session['order_id'] = order.id
            return render(request, self.template_name, self.get_context_data(order=order))

        # If cart is empty, redirect back to cart
        return redirect('cart:cart_detail')

    def get_context_data(self, order, **kwargs):
        context = super().get_context_data(**kwargs)
        cart = get_cart(self.request)
        base_currency = settings.DEFAULT_CURRENCY

        # Ensure payment exists
        if not hasattr(order, 'payment'):
            # Create payment if missing
            payment = Payment.objects.create(
                order=order,
                amount=order.total,
                currency=order.currency,
                status='PENDING'
            )
            order.payment = payment
            order.save()



        # Get currency options
        currency_options = []
        for code, name in settings.CURRENCIES:
            if code == base_currency:
                rate = 1.0
            else:
                # Try to get from cache or database
                cache_key = f'rate_{base_currency}_{code}'
                rate = cache.get(cache_key)
                if rate is None:
                    # Try database
                    try:
                        db_rate = CurrencyRate.objects.get(
                            base_currency=base_currency,
                            target_currency=code
                        ).rate
                        rate = float(db_rate)
                        cache.set(cache_key, rate, settings.CURRENCY_CACHE_TIMEOUT)
                    except CurrencyRate.DoesNotExist:
                        rate = get_exchange_rate(base_currency, code)

            currency_options.append({
                'code': code,
                'name': name,
                'rate': rate,
                'symbol': settings.CURRENCY_SYMBOLS.get(code, code)
            })

        context.update({
            'order': order,
            'payment': order.payment,
            'cart': cart,
            'prioritized_methods': get_prioritized_payment_methods(self.request),
            'currency_options': currency_options,
            'default_currency': base_currency,
            'default_currency_symbol': settings.CURRENCY_SYMBOLS.get(base_currency, base_currency),
        })
        return context

def get_country_name(country_code):
    # Implement country code to name conversion
    country_map = {'KE': 'Kenya', 'US': 'United States', 'GB': 'United Kingdom'}
    return country_map.get(country_code, country_code)

