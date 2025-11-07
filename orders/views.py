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
        form = ShippingForm(request.POST, user=request.user)

        if form.is_valid():
            try:
                with transaction.atomic():
                    # Check if user selected a saved address
                    saved_address = form.cleaned_data.get('saved_address')

                    # Create order instance
                    order = form.save(commit=False)
                    order.user = request.user

                    # Populate order fields from saved address if selected
                    if saved_address:
                        if saved_address.full_name:
                            parts = saved_address.full_name.split()
                            order.first_name = parts[0]
                            order.last_name = ' '.join(parts[1:]) if len(parts) > 1 else ''
                        else:
                            order.first_name = request.user.first_name
                            order.last_name = request.user.last_name

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
                    for cart_item in cart.items.select_related('product'):
                        product = cart_item.product

                        # Check stock
                        if cart_item.quantity > product.stock:
                            raise ValueError(
                                f"Insufficient stock for {product.name}. "
                                f"Only {product.stock} available."
                            )

                        # Get current price
                        current_price = product.get_display_price()
                        if not isinstance(current_price, Money):
                            current_price = Money(
                                Decimal(str(current_price)),
                                settings.DEFAULT_CURRENCY
                            )

                        # Subtotal
                        order_subtotal += current_price * cart_item.quantity

                        # Shipping
                        if not product.free_shipping and product.shipping_cost:
                            order_shipping += product.shipping_cost * cart_item.quantity

                        # Prepare order item
                        items_to_create.append(OrderItem(
                            order=order,
                            product=product,
                            price=current_price,
                            quantity=cart_item.quantity,
                        ))

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

                    # Handle saving new address - FIXED
                    save_address = form.cleaned_data.get('save_address')
                    address_nickname = form.cleaned_data.get('address_nickname', '').strip()

                    # Only save if requested AND not using a saved address
                    if save_address and address_nickname and not saved_address:
                        try:
                            # Check for duplicate address
                            from users.utils import duplicate_address_check

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
                                # Check if nickname already exists
                                nickname_exists = Address.objects.filter(
                                    user=request.user,
                                    nickname__iexact=address_nickname
                                ).exists()

                                if nickname_exists:
                                    # Generate unique nickname
                                    base_nickname = address_nickname
                                    counter = 1
                                    while Address.objects.filter(
                                        user=request.user,
                                        nickname__iexact=f"{base_nickname} {counter}"
                                    ).exists():
                                        counter += 1
                                    address_nickname = f"{base_nickname} {counter}"
                                    logger.info(
                                        f"Nickname '{base_nickname}' exists, using '{address_nickname}' instead"
                                    )

                                # Determine address type
                                nickname_lower = address_nickname.lower()
                                if 'home' in nickname_lower:
                                    address_type = 'home'
                                elif 'work' in nickname_lower or 'office' in nickname_lower:
                                    address_type = 'work'
                                elif 'bill' in nickname_lower:
                                    address_type = 'billing'
                                else:
                                    address_type = 'shipping'

                                # Check if this should be default
                                existing_addresses = Address.objects.filter(user=request.user)
                                is_default = not existing_addresses.exists()

                                # Create the address
                                new_address = Address.objects.create(
                                    user=request.user,
                                    nickname=address_nickname,
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

                                logger.info(
                                    f"Saved new address '{address_nickname}' (ID: {new_address.id}) "
                                    f"for user {request.user.id}"
                                )
                                messages.success(
                                    request,
                                    f"✓ Address '{address_nickname}' saved to your account!"
                                )

                        except IntegrityError as integrity_error:
                            # Handle unique constraint violation gracefully
                            logger.warning(
                                f"Could not save address due to constraint: {integrity_error}"
                            )
                            messages.info(
                                request,
                                "Order created successfully. Address was not saved (may already exist)."
                            )
                        except Exception as addr_error:
                            logger.warning(f"Failed to save address: {addr_error}")
                            messages.warning(
                                request,
                                "Order created successfully but address could not be saved."
                            )

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
                    messages.success(
                        request,
                        f"Order #{order.id} created successfully!"
                    )

                    logger.info(
                        f"Order {order.id} created successfully for user {request.user.email}"
                    )

                    return redirect('orders:checkout_order', order_id=order.id)

            except ValueError as ve:
                logger.warning(f"Order creation validation error: {str(ve)}")
                messages.error(request, str(ve))

            except Exception as e:
                logger.error(f"Unexpected error during order creation: {str(e)}", exc_info=True)
                messages.error(
                    request,
                    "An unexpected error occurred. Please try again or contact support."
                )

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

    # Common context (both GET and POST)
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


class OrderSuccessView(TemplateView):
    """Display order confirmation after successful payment."""
    template_name = "orders/success.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        order_id = self.kwargs.get("order_id")
        context["order"] = get_object_or_404(
            Order,
            id=order_id,
            user=self.request.user
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