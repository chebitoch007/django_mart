
import stripe
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


stripe.api_key = settings.STRIPE_SECRET_KEY

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

    # Stripe minimum amounts in cents (from https://stripe.com/docs/currencies)
    STRIPE_MINIMUMS = {
        'usd': 50,   # $0.50
        'kes': 50,   # KES 0.50
        'eur': 50,   # €0.50
        'gbp': 30,   # £0.30
        'ugx': 1000, # 1000 UGX
        'tzs': 1000, # 1000 TZS
    }

    def get(self, request, *args, **kwargs):
        order = self.get_order_from_session_or_cart(request)

        if not order:
            return redirect('cart:cart_detail')

        return render(request, self.template_name, self.get_context_data(order=order))

    def get_order_from_session_or_cart(self, request):
        order_id = request.session.get('order_id')
        if order_id:
            try:
                return Order.objects.get(id=order_id, user=request.user)
            except Order.DoesNotExist:
                pass

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
        cart = get_cart(self.request)
        base_currency = settings.DEFAULT_CURRENCY
        context['order'] = order
        context['cart'] = cart

        # Get prioritized methods
        prioritized_methods = get_prioritized_payment_methods(self.request)
        context['prioritized_methods'] = prioritized_methods

        # Get or initialize selected payment method in session
        selected_method = self.request.session.get(
            'selected_payment_method',
            prioritized_methods[0] if prioritized_methods else 'card'
        )
        context['selected_method'] = selected_method

        # Get or create payment
        payment, _ = Payment.objects.get_or_create(
            order=order,
            defaults={
                'amount': order.total,
                'currency': order.currency,
                'status': 'PENDING'
            }
        )
        context['payment'] = payment

        # Stripe PaymentIntent logic
        stripe_error = None
        payment_intent_client_secret = None
        amount_in_cents = int(payment.amount * 100)
        currency_lower = payment.currency.lower()
        min_amount = self.STRIPE_MINIMUMS.get(currency_lower, 50)

        if amount_in_cents < min_amount:
            stripe_error = (
                f"The amount is too small for {payment.currency} payments. "
                f"Minimum is {min_amount / 100:.2f} {payment.currency.upper()}."
            )
        else:
            try:
                intent = stripe.PaymentIntent.create(
                    amount=amount_in_cents,
                    currency=currency_lower,
                    automatic_payment_methods={"enabled": True},
                    metadata={
                        'order_id': order.id,
                        'payment_id': payment.id,
                        'user_id': self.request.user.id if self.request.user.is_authenticated else 'guest'
                    }
                )
                payment_intent_client_secret = intent.client_secret
            except stripe.error.StripeError as e:
                stripe_error = str(e)
            except Exception:
                stripe_error = "An error occurred while setting up payment. Please try again."
                logger.exception("Stripe PaymentIntent creation failed")


        # Prepare currency options
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
                        cache.set(cache_key, rate, settings.CURRENCY_CACHE_TIMEOUT)
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
            'STRIPE_PUBLIC_KEY': settings.STRIPE_PUBLIC_KEY,
            'payment_intent_client_secret': payment_intent_client_secret,
            'stripe_error': stripe_error,
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
    if method in ['card', 'paypal', 'mpesa', 'airtel']:
        request.session['selected_payment_method'] = method
        return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'invalid method'}, status=400)

