# orders/views.py - FIXED VERSION

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


@login_required
def create_order(request):
    """
    Creates an Order from cart with shipping cost calculation and saved address handling.
    """
    cart = get_cart(request)

    if not cart.items.exists():
        messages.info(request, "Your cart is empty. Add items before checkout.")
        return redirect('cart:cart_detail')

    if request.method == 'POST':
        # Check if using saved address
        saved_address_id = request.POST.get('saved_address')

        # If saved address selected, populate form data from it
        if saved_address_id and saved_address_id != '':
            try:
                saved_address = Address.objects.get(id=saved_address_id, user=request.user)

                # Create a mutable copy of POST data
                post_data = request.POST.copy()

                # Split full name
                name_parts = saved_address.full_name.split(maxsplit=1)
                post_data['first_name'] = name_parts[0] if name_parts else ''
                post_data['last_name'] = name_parts[1] if len(name_parts) > 1 else ''

                # Populate other fields
                post_data['email'] = request.user.email
                # Get phone and normalize it to include '+' before validation
                phone_number = saved_address.phone or getattr(request.user, 'phone_number', '')
                if phone_number and not phone_number.startswith('+') and phone_number.isdigit():
                    phone_number = '+' + phone_number
                post_data['phone'] = phone_number

                post_data['address'] = saved_address.street_address
                post_data['city'] = saved_address.city

                post_data['state'] = saved_address.state
                post_data['postal_code'] = saved_address.postal_code
                post_data['country'] = saved_address.country.code

                # Create form with populated data
                form = ShippingForm(post_data, user=request.user)
            except Address.DoesNotExist:
                messages.error(request, "Selected address not found.")
                return redirect('orders:create_order')
        else:
            form = ShippingForm(request.POST, user=request.user)

        if form.is_valid():
            try:
                with transaction.atomic():
                    # Get saved address reference
                    saved_address = form.cleaned_data.get('saved_address')

                    # Create order instance
                    order = form.save(commit=False)
                    order.user = request.user

                    # Populate from saved address if used
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

                    # Save order to generate primary key
                    order.save()

                    # Initialize totals
                    order_subtotal = Money(0, settings.DEFAULT_CURRENCY)
                    order_shipping = Money(0, settings.DEFAULT_CURRENCY)
                    items_to_create = []
                    products_to_update = []

                    # Process cart items
                    base_currency = settings.DEFAULT_CURRENCY

                    # Process cart items
                    for cart_item in cart.items.select_related('product'):
                        product = cart_item.product

                        # Check stock
                        if cart_item.quantity > product.stock:
                            raise ValueError(
                                f"Insufficient stock for {product.name}. "
                                f"Only {product.stock} available."
                            )

                        # --- CURRENCY CONVERSION FIX ---

                        # 1. Get Product Price and convert to Base Currency
                        current_price = product.price

                        if current_price.currency.code == base_currency:
                            converted_price = current_price
                        else:
                            # Use same cache logic as CheckoutView
                            cache_key = f"rate_{current_price.currency.code}_{base_currency}"
                            rate = cache.get(cache_key)
                            if rate is None:
                                rate = get_exchange_rate(current_price.currency.code, base_currency)
                                if rate is None:
                                    raise ValueError(
                                        f"Missing exchange rate: {current_price.currency.code} to {base_currency}")
                                cache.set(cache_key, float(rate), settings.CURRENCY_CACHE_TIMEOUT)

                            converted_price_amount = current_price.amount * Decimal(str(rate))
                            converted_price = Money(converted_price_amount, base_currency)

                        # 2. Add to Subtotal
                        order_subtotal += converted_price * cart_item.quantity

                        # 3. Get Shipping Cost and convert to Base Currency
                        converted_shipping = Money(0, base_currency)
                        if not product.free_shipping and product.shipping_cost:
                            shipping_cost = product.shipping_cost

                            if shipping_cost.currency.code == base_currency:
                                converted_shipping = shipping_cost
                            else:
                                # Use same cache logic
                                cache_key_ship = f"rate_{shipping_cost.currency.code}_{base_currency}"
                                rate_ship = cache.get(cache_key_ship)
                                if rate_ship is None:
                                    rate_ship = get_exchange_rate(shipping_cost.currency.code, base_currency)
                                    if rate_ship is None:
                                        raise ValueError(
                                            f"Missing exchange rate: {shipping_cost.currency.code} to {base_currency}")
                                    cache.set(cache_key_ship, float(rate_ship), settings.CURRENCY_CACHE_TIMEOUT)

                                converted_shipping_amount = shipping_cost.amount * Decimal(str(rate_ship))
                                converted_shipping = Money(converted_shipping_amount, base_currency)

                        # 4. Add to Shipping Total
                        order_shipping += converted_shipping * cart_item.quantity

                        # 5. Prepare Order Item (saving the converted price)
                        items_to_create.append(OrderItem(
                            order=order,
                            product=product,
                            price=converted_price,
                            quantity=cart_item.quantity,
                        ))

                        # --- END FIX ---

                        # Prepare product stock update
                        product.stock -= cart_item.quantity
                        products_to_update.append(product)

                    # Bulk operations
                    OrderItem.objects.bulk_create(items_to_create)
                    Product.objects.bulk_update(products_to_update, ['stock'])

                    # Save totals
                    order.shipping_cost = order_shipping
                    order.total = order_subtotal + order_shipping
                    order.save(update_fields=['shipping_cost', 'total'])

                    # Create payment record
                    try:
                        Payment.objects.create(
                            order=order,
                            amount=order.total,
                            original_amount=order.total,
                            converted_amount=order.total,
                            phone_number=order.phone,
                            status='PENDING',
                        )
                    except Exception as payment_error:
                        logger.error(f"Failed to create payment: {payment_error}")

                    # Handle saving new address (only if not using saved address)
                    save_address = form.cleaned_data.get('save_address')
                    address_nickname = form.cleaned_data.get('address_nickname', '').strip()

                    if save_address and address_nickname and not saved_address:
                        try:
                            from users.utils import duplicate_address_check, get_unique_address_nickname

                            existing = duplicate_address_check(
                                request.user,
                                order.address,
                                order.city,
                                order.postal_code
                            )

                            if existing:
                                messages.info(
                                    request,
                                    f"You already have this address saved as '{existing.nickname}'"
                                )
                            else:
                                # Get unique nickname
                                unique_nickname = get_unique_address_nickname(request.user, address_nickname)

                                # Determine address type
                                nickname_lower = unique_nickname.lower()
                                if 'home' in nickname_lower:
                                    address_type = 'home'
                                elif 'work' in nickname_lower or 'office' in nickname_lower:
                                    address_type = 'work'
                                elif 'bill' in nickname_lower:
                                    address_type = 'billing'
                                else:
                                    address_type = 'shipping'

                                # Check if should be default
                                is_default = not Address.objects.filter(user=request.user).exists()

                                # Create address
                                new_address = Address.objects.create(
                                    user=request.user,
                                    nickname=unique_nickname,
                                    address_type=address_type,
                                    full_name=f"{order.first_name} {order.last_name}",
                                    street_address=order.address,
                                    city=order.city,
                                    state=order.state,
                                    postal_code=order.postal_code,
                                    country=order.country,
                                    phone=order.phone,
                                    is_default=is_default,
                                )

                                logger.info(f"Saved new address '{unique_nickname}' for user {request.user.id}")
                                messages.success(request, f"✓ Address '{unique_nickname}' saved!")

                        except Exception as addr_error:
                            logger.warning(f"Failed to save address: {addr_error}")
                            messages.warning(request, "Order created but address could not be saved.")

                    # Clear cart
                    cart.items.all().delete()

                    # Store order in session
                    request.session['order_id'] = order.id
                    request.session.modified = True

                    # Send confirmation email
                    try:
                        order_created_email.delay(order.id)
                    except Exception as email_error:
                        logger.warning(f"Failed to queue order email: {email_error}")

                    # Success message
                    messages.success(request, f"Order #{order.id} created successfully!")
                    logger.info(f"Order {order.id} created for user {request.user.email}")

                    return redirect('orders:checkout_order', order_id=order.id)

            except ValueError as ve:
                logger.warning(f"Order validation error: {str(ve)}")
                messages.error(request, str(ve))

            except Exception as e:
                logger.error(f"Unexpected error during order creation: {str(e)}", exc_info=True)
                messages.error(request, "An unexpected error occurred. Please try again.")

        else:
            logger.warning(f"Shipping form validation failed: {form.errors}")
            messages.error(request, "Please correct the errors in the form below.")

    else:
        # GET request – prepopulate form
        initial_data = {
            'first_name': request.user.first_name,
            'last_name': request.user.last_name,
            'email': request.user.email,
            'phone': getattr(request.user, 'phone_number', ''),
        }

        # Load default or latest address
        default_address = (
                Address.objects.filter(user=request.user, is_default=True).first()
                or Address.objects.filter(user=request.user).order_by('-created').first()
        )

        if default_address:
            initial_data.update({
                'address': default_address.street_address,
                'city': default_address.city,
                'postal_code': default_address.postal_code,
                'state': default_address.state,
                'country': default_address.country,
                'phone': default_address.phone or initial_data['phone'],
            })

        form = ShippingForm(initial=initial_data, user=request.user)

        # Calculate estimated shipping
        total_shipping = Money(0, settings.DEFAULT_CURRENCY)
        for cart_item in cart.items.select_related('product'):
            if not cart_item.product.free_shipping and cart_item.product.shipping_cost:
                total_shipping += cart_item.product.shipping_cost * cart_item.quantity

    # Context for template
    saved_addresses = Address.objects.filter(user=request.user).order_by('-is_default', '-created')

    context = {
        'form': form,
        'cart': cart,
        'saved_addresses': saved_addresses,
        'has_addresses': saved_addresses.exists(),
        'estimated_shipping': locals().get('total_shipping', None),
    }

    return render(request, 'orders/shipping_form.html', context)


class OrderListView(LoginRequiredMixin, ListView):
    """Display paginated list of user's orders."""
    model = Order
    template_name = 'orders/history.html'
    context_object_name = 'orders'
    paginate_by = 10

    def get_queryset(self):
        """Fetch only current user's orders with optimized queries."""
        return (
            Order.objects.filter(user=self.request.user)
            .select_related('user')
            .prefetch_related('items')
            .only('id', 'created', 'status', 'total_currency', 'total', 'user__email')
            .order_by('-created')
        )


@login_required
def order_history(request):
    """Function-based view for order history."""
    orders = Order.objects.filter(user=request.user).order_by('-created')
    return render(request, 'orders/history.html', {'orders': orders})


class OrderDetailView(LoginRequiredMixin, DetailView):
    """Display detailed view of a single order."""
    model = Order
    template_name = 'orders/order_detail.html'
    context_object_name = 'order'

    def get_context_data(self, **kwargs):
        """Add payment information to context"""
        context = super().get_context_data(**kwargs)
        context['payment'] = getattr(self.object, 'payment', None)
        return context

    def _build_order_queryset(self):
        """Build optimized queryset with related data"""
        items_queryset = OrderItem.objects.select_related('product')
        return (
            Order.objects
            .select_related('user', 'payment')
            .prefetch_related(Prefetch('items', queryset=items_queryset))
        )

    def get_object(self, queryset=None):
        """Fetch order with security check."""
        pk = self.kwargs.get('pk')
        if not pk:
            raise Http404("Order ID not provided")

        try:
            pk = int(pk)
        except (ValueError, TypeError):
            logger.error(f"Invalid order ID format: {pk}")
            raise Http404("Invalid order ID")

        # Fetch order with permission check
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


class OrderSuccessView(LoginRequiredMixin, TemplateView): # <-- ADD LoginRequiredMixin
    """Display order confirmation after successful payment."""
    template_name = "orders/success.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        order_id = self.kwargs.get("order_id")
        context["order"] = get_object_or_404(
            Order,
            id=order_id,
            user=self.request.user  # This query will now work
        )
        return context

class CheckoutView(LoginRequiredMixin, TemplateView):
    """Payment checkout page with multi-currency and payment method selection."""
    template_name = 'orders/checkout.html'

    def get(self, request, order_id=None, *args, **kwargs):
        """Handle GET request for checkout page."""
        # If order_id is passed in URL, set it in session
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

        # Get order from session
        order = self.get_order_from_session(request)
        if not order:
            # Clear invalid session data
            request.session.pop('order_id', None)
            request.session.modified = True
            messages.info(request, "No pending order found. Please create an order first.")
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
        """Build context with payment options and currency conversion."""
        context = super().get_context_data(**kwargs)
        request = self.request
        base_currency = settings.DEFAULT_CURRENCY

        context.update({
            'order': order,
            'paypal_loaded': True,
        })

        # Get available payment methods
        prioritized_methods = get_prioritized_payment_methods(request)
        selected_method = request.session.get(
            'selected_payment_method',
            prioritized_methods[0] if prioritized_methods else 'mpesa'
        )

        context.update({
            'prioritized_methods': prioritized_methods,
            'selected_method': selected_method,
        })

        # Get or create payment object
        try:
            payment = order.payment
        except Payment.DoesNotExist:
            logger.warning(f"Payment missing for order {order.id}, creating now")
            payment = Payment.objects.create(
                order=order,
                amount=order.total,
                original_amount=order.total,
                converted_amount=order.total,
                phone_number=order.phone,
                status='PENDING',
            )

        # Sync payment amount with order total
        if payment.amount != order.total:
            payment.amount = order.total
            payment.save(update_fields=['amount'])

        context['payment'] = payment

        # Build currency options
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
            'default_currency_symbol': settings.CURRENCY_SYMBOLS.get(
                base_currency,
                base_currency
            ),
            'PAYPAL_CLIENT_ID': settings.PAYPAL_CLIENT_ID,
            'PAYSTACK_PUBLIC_KEY': settings.PAYSTACK_PUBLIC_KEY,
        })

        return context


@login_required
@require_POST
def update_payment_method(request):
    """AJAX endpoint to update selected payment method."""
    method = request.POST.get('method')

    # Validate payment method
    if method in ['paypal', 'mpesa']:
        request.session['selected_payment_method'] = method
        request.session.modified = True
        return JsonResponse({'status': 'success'})

    return JsonResponse({'status': 'invalid method'}, status=400)