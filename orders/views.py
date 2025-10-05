import logging
from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.http import Http404, JsonResponse
from django.views.decorators.http import require_POST
from django.views.generic import ListView, DetailView, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, render, redirect
from django.db.models import Prefetch
from cart.utils import get_cart
from asai import settings
from payment.models import Payment
from .models import Order, OrderItem, CurrencyRate
from django.contrib.auth.decorators import login_required
from payment.utils import get_prioritized_payment_methods
from core.utils import get_exchange_rate
from django import forms


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

            # Create payment for the order (SIMPLIFIED)
            payment = Payment.objects.create(
                order=order,
                amount=cart.total_price,
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
        ).select_related('user').prefetch_related('items').only(
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
        items_queryset = OrderItem.objects.select_related('product').only(
            'price', 'quantity', 'product__id', 'product__name', 'product__price'
        )

        return (Order.objects
        .select_related('user')
        .prefetch_related(
            Prefetch('items', queryset=items_queryset)
        )
        .only(
            *self.ORDER_FIELDS,
            *self.USER_FIELDS
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
        order = self.get_order_from_session_or_cart(request)
        if not order:
            request.session.pop('order_id', None)
            return redirect('cart:cart_detail')
        return render(request, self.template_name, self.get_context_data(order=order))

    def get_order_from_session_or_cart(self, request):
        order_id = request.session.get('order_id')
        if order_id:
            try:
                return Order.objects.get(id=order_id, user=request.user)
            except Order.DoesNotExist:
                request.session.pop('order_id', None)

        cart = get_cart(request)
        if cart.items.exists():
            order = Order.objects.create(
                user=request.user if request.user.is_authenticated else None,
                total=cart.total_price,
                currency=settings.DEFAULT_CURRENCY,
            )
            request.session['order_id'] = order.id
            return order
        return None

    def get_context_data(self, order, **kwargs):
        context = super().get_context_data(**kwargs)
        request = self.request
        cart = get_cart(request)
        base_currency = settings.DEFAULT_CURRENCY

        context.update({
            'order': order,
            'cart': cart,
            'paypal_loaded': True,
        })

        # --- Payment Methods ---
        prioritized_methods = get_prioritized_payment_methods(request)
        selected_method = request.session.get(
            'selected_payment_method',
            prioritized_methods[0] if prioritized_methods else 'mpesa'
        )

        context.update({
            'prioritized_methods': prioritized_methods,
            'selected_method': selected_method,
        })

        # --- Payment ---
        payment, _ = Payment.objects.get_or_create(
            order=order,
            defaults={'amount': order.total, 'currency': order.currency, 'status': 'PENDING'}
        )
        if payment.amount != order.total:
            payment.amount = order.total
            payment.save(update_fields=['amount'])
        context['payment'] = payment

        # --- Currency options ---
        currency_options = []
        for code, name in settings.CURRENCIES:
            if code == base_currency:
                rate = 1.0
            else:
                cache_key = f'rate_{base_currency}_{code}'
                rate = cache.get(cache_key)
                if rate is None:
                    try:
                        db_rate = CurrencyRate.objects.get(
                            base_currency=base_currency,
                            target_currency=code
                        ).rate
                        rate = float(db_rate)
                    except CurrencyRate.DoesNotExist:
                        rate = get_exchange_rate(base_currency, code)
                    cache.set(cache_key, rate, settings.CURRENCY_CACHE_TIMEOUT)

            currency_options.append({
                'code': code,
                'name': name,
                'rate': rate,
                'symbol': settings.CURRENCY_SYMBOLS.get(code, code)
            })

        context.update({
            'currency_options': currency_options,
            'default_currency': base_currency,
            'default_currency_symbol': settings.CURRENCY_SYMBOLS.get(base_currency, base_currency),
            'PAYPAL_CLIENT_ID': settings.PAYPAL_CLIENT_ID,
        })

        return context




def get_country_name(country_code):
    # Implement country code to name conversion
    country_map = {'KE': 'Kenya', 'US': 'United States', 'GB': 'United Kingdom'}
    return country_map.get(country_code, country_code)

@login_required
@require_POST
def update_payment_method(request):
    method = request.POST.get('method')
    if method in ['paypal', 'mpesa']:  # Removed 'card' and 'airtel' options
        request.session['selected_payment_method'] = method
        return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'invalid method'}, status=400)





