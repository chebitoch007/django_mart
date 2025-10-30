#orders/views.py

from djmoney.money import Money
from decimal import Decimal
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
from django.contrib.auth.decorators import login_required

from cart.utils import get_cart
from payment.models import Payment
from store.models import Product
from .models import Order, OrderItem
from payment.utils import get_prioritized_payment_methods
from core.utils import get_exchange_rate
from .forms import ShippingForm
from .tasks import order_created_email

logger = logging.getLogger(__name__)


@login_required
@transaction.atomic
def create_order(request):
    """
    Creates an Order and related OrderItems from the user's cart,
    using django-money for price and total handling.
    """
    cart = get_cart(request)
    if not cart.items.exists():
        return redirect('cart:cart_detail')

    if request.method == 'POST':
        form = ShippingForm(request.POST)
        if form.is_valid():
            order = form.save(commit=False)
            if request.user.is_authenticated:
                order.user = request.user
            order.save()

            order_total = Money(0, settings.DEFAULT_CURRENCY)
            items_to_create = []
            products_to_update = []

            try:
                for cart_item in cart.items.select_related('product'):
                    product = cart_item.product

                    # Check stock
                    if cart_item.quantity > product.stock:
                        form.add_error(None,
                                       f"Insufficient stock for {product.name}. Only {product.stock} left.")
                        raise transaction.TransactionManagementError()

                    # Get price as Money
                    current_price = product.get_display_price()
                    if not isinstance(current_price, Money):
                        logger.warning(
                            f"product.get_display_price() returned {type(current_price)}; coercing to Money."
                        )
                        current_price = Money(Decimal(current_price), settings.DEFAULT_CURRENCY)

                    # Accumulate total
                    order_total += current_price * cart_item.quantity

                    # Prepare OrderItem
                    items_to_create.append(OrderItem(
                        order=order,
                        product=product,
                        price=current_price,
                        quantity=cart_item.quantity,
                    ))

                    # Decrement stock
                    product.stock -= cart_item.quantity
                    products_to_update.append(product)

                # Bulk operations
                OrderItem.objects.bulk_create(items_to_create)
                Product.objects.bulk_update(products_to_update, ['stock'])

                # Save total
                order.total = order_total
                order.save(update_fields=['total'])

                # Create Payment
                Payment.objects.create(
                    order=order,
                    amount=order.total,
                    original_amount=order.total,
                    converted_amount=order.total,
                    phone_number=order.phone,
                    status='PENDING',
                )

                # Clear cart and send confirmation
                cart.items.all().delete()
                request.session['order_id'] = order.id
                order_created_email.delay(order.id)

                return redirect('orders:checkout')

            except transaction.TransactionManagementError:
                logger.error("Transaction failed during order creation.")
                transaction.set_rollback(True)

    else:
        initial_data = {}
        if request.user.is_authenticated:
            initial_data = {
                'first_name': request.user.first_name,
                'last_name': request.user.last_name,
                'email': request.user.email,
                'phone': getattr(request.user, 'phone_number', ''),
            }
        form = ShippingForm(initial=initial_data)

    return render(request, 'orders/shipping_form.html', {
        'form': form,
        'cart': cart
    })


class OrderListView(LoginRequiredMixin, ListView):
    model = Order
    template_name = 'orders/history.html'
    context_object_name = 'orders'
    paginate_by = 10

    def get_queryset(self):
        return (
            Order.objects.filter(user=self.request.user)
            .select_related('user')
            .prefetch_related('items')
            .only('id', 'created', 'status', 'total_currency', 'total', 'user__email')
            .order_by('-created')
        )


@login_required
def order_history(request):
    orders = Order.objects.filter(user=request.user).order_by('-created')
    return render(request, 'orders/history.html', {'orders': orders})

class OrderDetailView(LoginRequiredMixin, DetailView):
    model = Order
    template_name = 'orders/order_detail.html'
    context_object_name = 'order'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['payment'] = getattr(self.object, 'payment', None)
        return context

    def _build_order_queryset(self):
        items_queryset = OrderItem.objects.select_related('product')
        return (
            Order.objects
            .select_related('user', 'payment')
            .prefetch_related(Prefetch('items', queryset=items_queryset))
        )

    def get_object(self, queryset=None):
        pk = self.kwargs.get('pk')
        if not pk:
            raise Http404("Order ID not provided")

        try:
            pk = int(pk)
        except (ValueError, TypeError):
            logger.error(f"Invalid order ID format: {pk}")
            raise Http404("Invalid order ID")

        order = (
            self._build_order_queryset()
            .filter(pk=pk, user=self.request.user)
            .first()
        )

        if not order:
            logger.warning(f"Order {pk} not found for user {self.request.user.username}")
            raise Http404("Order not found or you don't have permission to view it")

        return order


class OrderSuccessView(TemplateView):
    template_name = "orders/success.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        order_id = self.kwargs.get("order_id")
        context["order"] = get_object_or_404(Order, id=order_id, user=self.request.user)
        return context


class CheckoutView(LoginRequiredMixin, TemplateView):
    template_name = 'orders/checkout.html'

    def get(self, request, *args, **kwargs):
        order = self.get_order_from_session(request)
        if not order:
            request.session.pop('order_id', None)
            return redirect('cart:cart_detail')
        return render(request, self.template_name, self.get_context_data(order=order))

    def get_order_from_session(self, request):
        order_id = request.session.get('order_id')
        if not order_id:
            return None
        try:
            # --- OPTIMIZED QUERY ---
            items_queryset = OrderItem.objects.select_related('product')
            order = (
                Order.objects
                .prefetch_related(Prefetch('items', queryset=items_queryset))
                .get(id=order_id, user=request.user)
            )
            # --- END OPTIMIZATION ---

            if not order.is_payable:
                request.session.pop('order_id', None)
                return None
            return order
        except Order.DoesNotExist:
            request.session.pop('order_id', None)
            return None


    def get_context_data(self, order, **kwargs):
        context = super().get_context_data(**kwargs)
        request = self.request
        base_currency = settings.DEFAULT_CURRENCY

        context.update({
            'order': order,
            'paypal_loaded': True,
        })

        prioritized_methods = get_prioritized_payment_methods(request)
        selected_method = request.session.get(
            'selected_payment_method',
            prioritized_methods[0] if prioritized_methods else 'mpesa'
        )

        context.update({
            'prioritized_methods': prioritized_methods,
            'selected_method': selected_method,
        })

        payment = order.payment

        if payment.amount != order.total:
            payment.amount = order.total
            payment.save(update_fields=['amount'])
        context['payment'] = payment

        currency_options = []

        for code in settings.CURRENCIES:
            name = settings.CURRENCY_NAMES.get(code, code)
            symbol = settings.CURRENCY_SYMBOLS.get(code, code)

            if code == base_currency:
                rate = 1.0
            else:
                cache_key = f"rate_{base_currency}_{code}"
                rate = cache.get(cache_key)
                if rate is None:
                    rate = get_exchange_rate(base_currency, code)
                    cache.set(cache_key, float(rate), settings.CURRENCY_CACHE_TIMEOUT)

            currency_options.append({
                'code': code,
                'name': name,
                'symbol': symbol,
                'rate': float(rate),
            })

        context.update({
            'currency_options': currency_options,
            'default_currency': base_currency,
            'default_currency_symbol': settings.CURRENCY_SYMBOLS.get(base_currency, base_currency),
            'PAYPAL_CLIENT_ID': settings.PAYPAL_CLIENT_ID,
        })

        return context


@login_required
@require_POST
def update_payment_method(request):
    method = request.POST.get('method')
    if method in ['paypal', 'mpesa']:
        request.session['selected_payment_method'] = method
        return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'invalid method'}, status=400)
