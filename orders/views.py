# orders/views.py

from users.models import Address
from djmoney.money import Money
from decimal import Decimal
import logging
from django.conf import settings
from django.core.cache import cache
from django.db import transaction, IntegrityError
from django.http import Http404, JsonResponse
from django.views.decorators.http import require_POST
from django.views.generic import ListView, DetailView, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, render, redirect
from django.db.models import Prefetch
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from cart.utils import get_cart
from payment.models import Payment
from store.models import Product
from .models import Order, OrderItem
from payment.utils import get_prioritized_payment_methods
from core.utils import get_exchange_rate
from .forms import ShippingForm
from .tasks import order_created_email

logger = logging.getLogger(__name__)


def get_user_currency(request):
    """Get user's selected currency from session or default"""
    return request.session.get('user_currency', settings.DEFAULT_CURRENCY)


@login_required
def create_order(request):
    """
    Creates an Order from cart.
    ✅ FIXED: Correctly prioritizes discount_price using get_display_price().
    ✅ FIXED: Corrected indentation logic for price calculation.
    """
    cart = get_cart(request)

    if not cart.items.exists():
        messages.info(request, "Your cart is empty. Add items before checkout.")
        return redirect('cart:cart_detail')

    db_currency = settings.DEFAULT_CURRENCY
    form = None  # Initialize form variable

    if request.method == 'POST':
        # --- POST REQUEST HANDLING ---
        saved_address_id = request.POST.get('saved_address')

        if saved_address_id and saved_address_id != '':
            try:
                saved_address = Address.objects.get(id=saved_address_id, user=request.user)
                post_data = request.POST.copy()

                # Helper to split names safely
                name_parts = saved_address.full_name.split(maxsplit=1)
                post_data['first_name'] = name_parts[0] if name_parts else ''
                post_data['last_name'] = name_parts[1] if len(name_parts) > 1 else ''
                post_data['email'] = request.user.email

                # Helper to ensure phone format
                phone_number = saved_address.phone or getattr(request.user, 'phone_number', '')
                if phone_number and not phone_number.startswith('+') and phone_number.isdigit():
                    phone_number = '+' + phone_number
                post_data['phone'] = phone_number

                post_data['address'] = saved_address.street_address
                post_data['city'] = saved_address.city
                post_data['state'] = saved_address.state
                post_data['postal_code'] = saved_address.postal_code
                post_data['country'] = saved_address.country.code

                form = ShippingForm(post_data, user=request.user)

            except Address.DoesNotExist:
                messages.error(request, "Selected address not found.")
                # Fall through to re-render (will generate new blank form below if needed)
                form = ShippingForm(request.POST, user=request.user)
        else:
            form = ShippingForm(request.POST, user=request.user)

        if form.is_valid():
            try:
                with transaction.atomic():
                    saved_address = form.cleaned_data.get('saved_address')

                    # Create order instance
                    order = form.save(commit=False)
                    order.user = request.user

                    # Initialize totals in Default Currency (KES)
                    order.total = Money(0, db_currency)
                    order.shipping_cost = Money(0, db_currency)

                    # Handle Address Overrides
                    if saved_address:
                        name_parts = saved_address.full_name.split(maxsplit=1)
                        order.first_name = name_parts[0] if name_parts else request.user.first_name
                        order.last_name = name_parts[1] if len(name_parts) > 1 else request.user.last_name
                        order.phone = saved_address.phone or getattr(request.user, 'phone_number', '')
                        order.address = saved_address.street_address
                        order.city = saved_address.city
                        order.state = saved_address.state
                        order.postal_code = saved_address.postal_code
                        order.country = saved_address.country

                    order.save()

                    # Calculate Totals
                    order_subtotal = Money(0, db_currency)
                    order_shipping = Money(0, db_currency)
                    items_to_create = []
                    products_to_update = []

                    for cart_item in cart.items.select_related('product'):
                        product = cart_item.product

                        # 1. Check Stock
                        if cart_item.quantity > product.stock:
                            raise ValueError(f"Insufficient stock for {product.name}")

                        # 2. Determine Price (Use Discount Price if available)
                        # get_display_price() logic: returns discount_price if set, else price
                        effective_price = product.get_display_price()

                        # 3. Convert to Default Currency (if product currency differs from DB currency)
                        if effective_price.currency.code != db_currency:
                            rate = get_exchange_rate(effective_price.currency.code, db_currency)
                            if rate:
                                converted_amount = effective_price.amount * Decimal(str(rate))
                                final_item_price = Money(converted_amount, db_currency)
                            else:
                                final_item_price = Money(effective_price.amount, db_currency)
                        else:
                            final_item_price = effective_price

                        # 4. Add to Order Subtotal
                        order_subtotal += final_item_price * cart_item.quantity

                        # 5. Handle Shipping Cost
                        item_shipping = Money(0, db_currency)
                        if not product.free_shipping and product.shipping_cost:
                            ship_cost = product.shipping_cost
                            if ship_cost.currency.code != db_currency:
                                rate = get_exchange_rate(ship_cost.currency.code, db_currency)
                                if rate:
                                    converted_ship = ship_cost.amount * Decimal(str(rate))
                                    item_shipping = Money(converted_ship, db_currency)
                            else:
                                item_shipping = ship_cost

                        order_shipping += item_shipping * cart_item.quantity

                        items_to_create.append(OrderItem(
                            order=order,
                            product=product,
                            price=final_item_price,
                            quantity=cart_item.quantity,
                        ))

                        product.stock -= cart_item.quantity
                        products_to_update.append(product)

                    # Bulk Create & Update
                    OrderItem.objects.bulk_create(items_to_create)
                    Product.objects.bulk_update(products_to_update, ['stock'])

                    # Finalize Order Totals
                    order.shipping_cost = order_shipping
                    order.total = order_subtotal + order_shipping
                    order.save(update_fields=['shipping_cost', 'total'])

                    logger.info(f"Order {order.id} created. Base Currency: {db_currency}, Total: {order.total}")

                    # Create Payment Record
                    try:
                        Payment.objects.create(
                            order=order,
                            amount=order.total,
                            original_amount=order.total,
                            converted_amount=order.total,
                            phone_number=order.phone,
                            status='PENDING',
                        )
                    except Exception as e:
                        logger.error(f"Payment creation failed: {e}")

                    # Address Saving Logic
                    save_address_opt = form.cleaned_data.get('save_address')
                    nickname = form.cleaned_data.get('address_nickname', '').strip()

                    if save_address_opt and nickname and not saved_address:
                        try:
                            from users.utils import duplicate_address_check, get_unique_address_nickname
                            existing = duplicate_address_check(
                                request.user, order.address, order.city, order.postal_code
                            )
                            if not existing:
                                unique_nickname = get_unique_address_nickname(request.user, nickname)
                                Address.objects.create(
                                    user=request.user,
                                    nickname=unique_nickname,
                                    address_type='shipping',
                                    full_name=f"{order.first_name} {order.last_name}",
                                    street_address=order.address,
                                    city=order.city,
                                    state=order.state,
                                    postal_code=order.postal_code,
                                    country=order.country,
                                    phone=order.phone,
                                    is_default=False,
                                )
                        except Exception as addr_err:
                            logger.warning(f"Failed to auto-save address: {addr_err}")

                    # Cleanup
                    cart.items.all().delete()
                    request.session['order_id'] = order.id

                    try:
                        order_created_email.delay(order.id)
                    except Exception:
                        pass

                    messages.success(request, f"Order #{order.id} created successfully!")
                    # ✅ RETURN SUCCESS RESPONSE
                    return redirect('orders:checkout_order', order_id=order.id)

            except ValueError as ve:
                messages.error(request, str(ve))
            except Exception as e:
                logger.error(f"Order error: {e}", exc_info=True)
                messages.error(request, "An error occurred. Please try again.")
        else:
            messages.error(request, "Please correct the errors in the form.")

    else:
        # --- GET REQUEST HANDLING ---
        initial_data = {
            'first_name': request.user.first_name,
            'last_name': request.user.last_name,
            'email': request.user.email,
            'phone': getattr(request.user, 'phone_number', ''),
        }

        saved_addresses = Address.objects.filter(user=request.user).order_by('-is_default', '-created')
        if saved_addresses.exists():
            default_addr = saved_addresses.first()
            if default_addr.is_default:
                initial_data.update({
                    'address': default_addr.street_address,
                    'city': default_addr.city,
                    'postal_code': default_addr.postal_code,
                    'state': default_addr.state,
                    'country': default_addr.country,
                    'phone': default_addr.phone or initial_data['phone'],
                })

        form = ShippingForm(initial=initial_data, user=request.user)

    # --- COMMON RENDER LOGIC (Executes for GET or Failed POST) ---
    # 1. Get User's Saved Addresses
    saved_addresses = Address.objects.filter(user=request.user).order_by('-is_default', '-created')

    # 2. Calculate Display Totals
    user_currency = get_user_currency(request)

    # Calculate estimated totals for display
    cart_subtotal = cart.get_total_price_in_currency(user_currency)

    # Calculate shipping estimate in user currency
    estimated_shipping_display = Money(0, user_currency)
    for item in cart.items.all():
        if not item.product.free_shipping and item.product.shipping_cost:
            ship_cost = item.product.shipping_cost
            # Convert if needed
            if ship_cost.currency.code != user_currency:
                rate = get_exchange_rate(ship_cost.currency.code, user_currency) or 1.0
                conv_ship = ship_cost.amount * Decimal(str(rate))
                ship_cost = Money(conv_ship, user_currency)
            estimated_shipping_display += ship_cost * item.quantity

    cart_grand_total = Money(cart_subtotal.amount + estimated_shipping_display.amount, user_currency)

    context = {
        'form': form,
        'cart': cart,
        'saved_addresses': saved_addresses,
        'has_addresses': saved_addresses.exists(),
        'cart_subtotal': cart_subtotal,
        'cart_shipping': estimated_shipping_display,
        'cart_grand_total': cart_grand_total,
        'user_currency': user_currency,
        'estimated_shipping': estimated_shipping_display,
    }

    # ✅ RETURN RENDER RESPONSE
    return render(request, 'orders/shipping_form.html', context)


class CheckoutView(LoginRequiredMixin, TemplateView):
    """
    Payment checkout page.
    ✅ FIXED: Calculates rates relative to the Order's Base Currency (KES).
    """
    template_name = 'orders/checkout.html'

    def get(self, request, order_id=None, *args, **kwargs):
        """Handle GET request for checkout page."""
        if order_id:
            try:
                order = Order.objects.get(id=order_id, user=request.user)
                if order.is_payable:
                    request.session['order_id'] = order_id
                    request.session.modified = True
                else:
                    messages.warning(request, "This order is not available for payment.")
                    return redirect('orders:order_detail', pk=order_id)
            except Order.DoesNotExist:
                messages.error(request, "Order not found.")
                return redirect('orders:order_list')

        order = self.get_order_from_session(request)
        if not order:
            return redirect('cart:cart_detail')

        return render(request, self.template_name, self.get_context_data(order=order))

    def get_order_from_session(self, request):
        """Retrieve order from session with validation."""
        order_id = request.session.get('order_id')
        if not order_id:
            return None

        try:
            items_queryset = OrderItem.objects.select_related('product')
            order = (
                Order.objects
                .prefetch_related(Prefetch('items', queryset=items_queryset))
                .get(id=order_id, user=request.user)
            )

            if not order.is_payable:
                request.session.pop('order_id', None)
                request.session.modified = True
                return None

            return order
        except Order.DoesNotExist:
            request.session.pop('order_id', None)
            request.session.modified = True
            return None

    def get_context_data(self, order, **kwargs):
        context = super().get_context_data(**kwargs)
        request = self.request

        # This is now guaranteed to be DEFAULT_CURRENCY (e.g., KES) because of create_order
        base_currency = order.total.currency.code

        logger.info(f"[CheckoutView] Order {order.id} - Base Currency: {base_currency}, Amount: {order.total.amount}")

        # Payment logic
        prioritized_methods = get_prioritized_payment_methods(self.request)
        selected_method = request.session.get(
            'selected_payment_method',
            prioritized_methods[0] if prioritized_methods else 'mpesa'
        )

        # Ensure Payment record exists and is synced
        try:
            payment = order.payment
        except Payment.DoesNotExist:
            payment = Payment.objects.create(
                order=order,
                provider='PENDING',
                amount=order.total,
                original_amount=order.total,
                converted_amount=order.total,
                phone_number=order.phone,
                status='PENDING',
            )

        # Force sync if amounts drifted
        if payment.amount != order.total:
            payment.amount = order.total
            payment.original_amount = order.total
            payment.converted_amount = order.total
            payment.save(update_fields=['amount', 'original_amount', 'converted_amount'])

        # ✅ GENERATE RATES RELATIVE TO BASE CURRENCY (KES)
        # This ensures that if Base is 1500 KES, and user selects EUR,
        # The frontend receives rate ~0.007. Result: 10.5 EUR.
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
                    if rate:
                        cache.set(cache_key, float(rate), settings.CURRENCY_CACHE_TIMEOUT)
                    else:
                        rate = 1.0  # Fallback
                        logger.warning(f"Missing exchange rate: {base_currency} -> {code}")

            currency_options.append({
                'code': code,
                'name': name,
                'symbol': symbol,
                'rate': float(rate),
            })

        context.update({
            'order': order,
            'payment': payment,
            'currency_options': currency_options,
            'prioritized_methods': prioritized_methods,
            'selected_method': selected_method,
            'PAYPAL_CLIENT_ID': settings.PAYPAL_CLIENT_ID,
            'PAYSTACK_PUBLIC_KEY': settings.PAYSTACK_PUBLIC_KEY,
            # Base currency is now the "Master" currency for the template
            'user_currency': base_currency,
            'order_currency': base_currency,
        })

        return context


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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['user_currency'] = get_user_currency(self.request)
        return context


@login_required
def order_history(request):
    """Function-based view for order history."""
    orders = Order.objects.filter(user=request.user).order_by('-created')
    return render(request, 'orders/history.html', {'orders': orders})


class OrderDetailView(LoginRequiredMixin, DetailView):
    model = Order
    template_name = 'orders/order_detail.html'
    context_object_name = 'order'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['payment'] = getattr(self.object, 'payment', None)
        context['user_currency'] = self.object.total.currency.code
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
            logger.warning(
                f"Order {pk} not found or unauthorized access by user "
                f"{self.request.user.username}"
            )
            raise Http404("Order not found or you don't have permission to view it")

        return order


class OrderSuccessView(LoginRequiredMixin, TemplateView):
    """Display order confirmation after successful payment."""
    template_name = "orders/success.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        order_id = self.kwargs.get("order_id")
        order = get_object_or_404(Order, id=order_id, user=self.request.user)

        # Pass explicit currency info
        context.update({
            "order": order,
            "user_currency": order.total.currency.code,
            "order_currency": order.total.currency.code,
        })
        return context


@login_required
@require_POST
def update_payment_method(request):
    """AJAX endpoint to update selected payment method."""
    method = request.POST.get('method')

    if method in ['paypal', 'mpesa', 'paystack']:
        request.session['selected_payment_method'] = method
        request.session.modified = True
        return JsonResponse({'status': 'success'})

    return JsonResponse({'status': 'invalid method'}, status=400)