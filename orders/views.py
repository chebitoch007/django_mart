# orders/views.py - FIXED VERSION

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
    Creates an Order and related OrderItems from the user's cart.

    FIXED: Enhanced error handling and redirect reliability
    """
    # Get user's shopping cart
    cart = get_cart(request)

    # Redirect if cart is empty
    if not cart.items.exists():
        messages.info(request, "Your cart is empty. Add items before checkout.")
        return redirect('cart:cart_detail')

    if request.method == 'POST':
        form = ShippingForm(request.POST)

        if form.is_valid():
            try:
                # Use atomic transaction with explicit handling
                with transaction.atomic():
                    # Create order instance without saving to DB yet
                    order = form.save(commit=False)

                    # Associate authenticated user with order
                    if request.user.is_authenticated:
                        order.user = request.user

                    # Save order to generate primary key
                    order.save()

                    # Initialize order total
                    order_total = Money(0, settings.DEFAULT_CURRENCY)
                    items_to_create = []
                    products_to_update = []

                    # Process each cart item
                    for cart_item in cart.items.select_related('product'):
                        product = cart_item.product

                        # CRITICAL: Validate stock availability
                        if cart_item.quantity > product.stock:
                            form.add_error(
                                None,
                                f"Insufficient stock for {product.name}. "
                                f"Only {product.stock} available."
                            )
                            # Explicitly raise to trigger rollback
                            raise ValueError(f"Insufficient stock for {product.name}")

                        # Get current product price as Money object
                        current_price = product.get_display_price()

                        # Ensure price is Money type for consistency
                        if not isinstance(current_price, Money):
                            logger.warning(
                                f"Product {product.id} price is {type(current_price)}, "
                                f"converting to Money"
                            )
                            current_price = Money(
                                Decimal(str(current_price)),
                                settings.DEFAULT_CURRENCY
                            )

                        # Accumulate order total
                        order_total += current_price * cart_item.quantity

                        # Prepare OrderItem for bulk creation
                        items_to_create.append(OrderItem(
                            order=order,
                            product=product,
                            price=current_price,
                            quantity=cart_item.quantity,
                        ))

                        # Prepare product stock update
                        product.stock -= cart_item.quantity
                        products_to_update.append(product)

                    # Bulk create order items
                    OrderItem.objects.bulk_create(items_to_create)

                    # Bulk update product stock
                    Product.objects.bulk_update(products_to_update, ['stock'])

                    # Save calculated total to order
                    order.total = order_total
                    order.save(update_fields=['total'])

                    # Create Payment object for order
                    try:
                        Payment.objects.create(
                            order=order,
                            amount=order.total,
                            original_amount=order.total,
                            converted_amount=order.total,
                            phone_number=order.phone,
                            status='PENDING',
                        )
                        logger.info(f"Payment record created for order {order.id}")
                    except Exception as payment_error:
                        logger.error(f"Failed to create payment for order {order.id}: {payment_error}")
                        # Don't fail the entire order, payment can be created later
                        pass

                    # Clear user's cart after successful order creation
                    cart.items.all().delete()

                    # Store order ID in session for checkout page
                    request.session['order_id'] = order.id
                    # Force session save to ensure persistence
                    request.session.modified = True

                    # Send order confirmation email asynchronously
                    try:
                        order_created_email.delay(order.id)
                    except Exception as email_error:
                        logger.warning(f"Failed to queue order email: {email_error}")
                        # Don't fail order for email issues

                    # Success message
                    messages.success(
                        request,
                        f"Order #{order.id} created successfully! Proceeding to payment."
                    )

                    logger.info(f"Order {order.id} created successfully for user {request.user.username}")

                    # Redirect to checkout/payment page
                    return redirect('orders:checkout')

            except ValueError as ve:
                # Stock validation error - form error already added
                logger.warning(f"Order creation validation error: {str(ve)}")
                messages.error(
                    request,
                    "Unable to complete order. Please check item availability."
                )
                # Transaction automatically rolled back

            except Exception as e:
                # Catch all other errors
                logger.error(f"Unexpected error during order creation: {str(e)}", exc_info=True)
                messages.error(
                    request,
                    "An unexpected error occurred. Please try again or contact support."
                )
                # Transaction automatically rolled back

        else:
            # Form validation failed
            logger.warning(f"Shipping form validation failed: {form.errors}")
            messages.error(
                request,
                "Please correct the errors in the form below."
            )

    else:
        # GET request: Prepopulate form with user data
        initial_data = {}

        if request.user.is_authenticated:
            # Fetch user profile data for form prepopulation
            initial_data = {
                'first_name': request.user.first_name,
                'last_name': request.user.last_name,
                'email': request.user.email,
                'phone': getattr(request.user, 'phone_number', ''),
            }

            # If user has a profile with saved address, use it
            if hasattr(request.user, 'profile'):
                profile = request.user.profile
                initial_data.update({
                    'address': getattr(profile, 'address', ''),
                    'city': getattr(profile, 'city', ''),
                    'postal_code': getattr(profile, 'postal_code', ''),
                    'state': getattr(profile, 'state', ''),
                    'country': getattr(profile, 'country', 'KE'),
                })

        form = ShippingForm(initial=initial_data)

    # Render shipping form template
    context = {
        'form': form,
        'cart': cart,
    }

    return render(request, 'orders/shipping_form.html', context)


class OrderListView(LoginRequiredMixin, ListView):
    """
    Display paginated list of user's orders.
    """
    model = Order
    template_name = 'orders/history.html'
    context_object_name = 'orders'
    paginate_by = 10

    def get_queryset(self):
        """
        Fetch only current user's orders with optimized queries.
        """
        return (
            Order.objects.filter(user=self.request.user)
            .select_related('user')
            .prefetch_related('items')
            .only('id', 'created', 'status', 'total_currency', 'total', 'user__email')
            .order_by('-created')
        )


@login_required
def order_history(request):
    """
    Function-based view for order history.
    """
    orders = Order.objects.filter(user=request.user).order_by('-created')
    return render(request, 'orders/history.html', {'orders': orders})


class OrderDetailView(LoginRequiredMixin, DetailView):
    """
    Display detailed view of a single order.
    """
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
        """
        Fetch order with security check.
        """
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
    """
    Display order confirmation after successful payment.
    """
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
    """
    Payment checkout page with multi-currency and payment method selection.

    FIXED: Better session handling and error recovery
    """
    template_name = 'orders/checkout.html'

    def get(self, request, order_id=None, *args, **kwargs):
        """
        Handle GET request for checkout page.
        """
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
        """
        Retrieve order from session with validation.
        """
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
        """
        Build context with payment options and currency conversion.
        """
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
    """
    AJAX endpoint to update selected payment method.
    """
    method = request.POST.get('method')

    # Validate payment method
    if method in ['paypal', 'mpesa']:
        request.session['selected_payment_method'] = method
        request.session.modified = True
        return JsonResponse({'status': 'success'})

    return JsonResponse({'status': 'invalid method'}, status=400)