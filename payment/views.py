from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
import stripe
from django.core.mail import mail_admins
from decimal import Decimal
import requests
from .models import PaymentLog
from django.views.generic import DetailView, FormView, TemplateView, View, DeleteView, UpdateView, CreateView
from django.shortcuts import redirect, get_object_or_404, render
from django.contrib import messages
from django.db import transaction
from django.conf import settings
from .models import Payment, PaymentMethod
from orders.models import Order
from .forms import MobileMoneyVerificationForm, PaymentMethodForm, PayPalPaymentForm
from django.views.decorators.http import require_GET
from django.utils.decorators import method_decorator
from django.urls import reverse_lazy
from .services import PaymentProcessor
from .forms import PaymentProcessingForm
from core.utils import get_exchange_rate
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.shortcuts import reverse
import logging

stripe.api_key = settings.STRIPE_SECRET_KEY
logger = logging.getLogger(__name__)


@csrf_protect
@require_POST
@login_required
def process_payment(request, order_id):
    if request.headers.get('X-Debug') == 'true':
        logger.debug(f"Payment request for order {order_id}:")
        logger.debug(f"POST data: {request.POST}")
        logger.debug(f"User: {request.user}")

    user_key = f"payment_attempts_{request.user.id}"
    attempts = cache.get(user_key, 0)

    if attempts >= 5:
        return JsonResponse({
            'success': False,
            'error_message': 'Too many attempts. Please try again later.'
        }, status=429)

    # Increment attempt count (5-minute window)
    cache.set(user_key, attempts + 1, timeout=300)

    try:
        # Get order instance
        order = get_object_or_404(Order, id=order_id, user=request.user)

        # Use both path parameter and form data
        post_data = request.POST.copy()
        post_data['order_id'] = order_id  # Ensure order_id is always set

        # Add amount from order if missing
        if 'amount' not in post_data:
            post_data['amount'] = str(order.total_cost)

        form = PaymentProcessingForm(post_data, user=request.user)

        if not form.is_valid():
            error_msg = '; '.join(f"{field}: {errs[0]}" for field, errs in form.errors.items())
            return JsonResponse({'success': False, 'error_message': error_msg}, status=400)

        order = form.cleaned_data['order']
        payment_method = form.cleaned_data['payment_method']
        payment = order.payment  # Assumes a OneToOneField or FK from Order to Payment

        # Sanity check
        if order.user != request.user:
            raise PermissionDenied("Order does not belong to this user")

        # Check payment status
        if payment.status != 'PENDING':
            logger.warning(f"Duplicate payment attempt for order {order.id}, status: {payment.status}")
            PaymentLog.objects.create(
                payment=payment,
                log_type='FAILED',
                details={'reason': 'Duplicate attempt', 'user': request.user.id}
            )
            return JsonResponse({
                'success': False,
                'error_message': 'Order has already been processed'
            }, status=400)

        # Validate currency conversion rate
        conversion_rate = form.cleaned_data.get('conversion_rate', 1)
        if conversion_rate <= 0:
            logger.error(f"Invalid conversion rate: {conversion_rate} for order {order.id}")
            return JsonResponse({
                'success': False,
                'error_message': 'Invalid currency conversion rate'
            }, status=400)

        # Log processing start
        PaymentLog.objects.create(
            payment=payment,
            log_type='PROCESSING',
            details={
                'method': payment_method,
                'amount': form.cleaned_data['amount'],
                'currency': form.cleaned_data['currency'],
                'conversion_rate': conversion_rate
            }
        )

        if payment_method == 'card':
            return process_stripe_payment(request, order, payment, form.cleaned_data)

        elif payment_method == 'paypal':
            paypal_order_id = form.cleaned_data.get('paypal_order_id')
            paypal_payer_id = form.cleaned_data.get('paypal_payer_id')

            if not paypal_order_id or not paypal_payer_id:
                logger.error(f"Missing PayPal IDs for order {order.id}")
                return JsonResponse({
                    'success': False,
                    'error_message': 'Missing PayPal payment information'
                }, status=400)

            capture_result = capture_paypal_payment(paypal_order_id)

            if not capture_result.get('success'):
                logger.error(f"PayPal capture failed for order {order.id}: {capture_result.get('error')}")
                PaymentLog.objects.create(
                    payment=payment,
                    log_type='FAILED',
                    details={
                        'method': 'paypal',
                        'error': capture_result.get('error'),
                        'order_id': paypal_order_id
                    }
                )
                return JsonResponse({
                    'success': False,
                    'error_message': capture_result.get('error', 'PayPal payment failed')
                }, status=400)

            amount = payment.amount
            if form.cleaned_data['currency'] != payment.currency:
                rate = conversion_rate
                amount = round(amount * rate, 2)

            # Mark payment as complete
            payment.status = 'COMPLETED'
            payment.paid_at = timezone.now()
            payment.payment_method = 'paypal'
            payment.amount_paid = amount
            payment.transaction_id = paypal_order_id
            payment.save()

            order.status = 'PAID'
            order.save()

            PaymentLog.objects.create(
                payment=payment,
                log_type='SUCCESS',
                details={
                    'method': 'paypal',
                    'order_id': paypal_order_id,
                    'payer_id': paypal_payer_id,
                    'converted_amount': amount,
                    'from_currency': form.cleaned_data['currency'],
                    'to_currency': payment.currency,
                    'conversion_rate': conversion_rate
                }
            )

            redirect_url = reverse('payment:payment_complete', kwargs={'pk': order.id})
            return JsonResponse({'success': True, 'redirect_url': redirect_url})

        # Default: use generic processor
        processor = PaymentProcessor(payment=payment, **form.cleaned_data)
        result = processor.process()

        if result.get('success'):
            PaymentLog.objects.create(
                payment=payment,
                log_type='SUCCESS',
                details={'gateway_response': result.get('gateway_data', {})}
            )
            redirect_url = reverse('payment:payment_complete', kwargs={'pk': order.id})
            return JsonResponse({'success': True, 'redirect_url': redirect_url})
        else:
            PaymentLog.objects.create(
                payment=payment,
                log_type='FAILED',
                details={
                    'error_code': result.get('error_code'),
                    'error_message': result.get('error_message')
                }
            )
            return JsonResponse({
                'success': False,
                'error_code': result.get('error_code'),
                'error_message': result.get('error_message')
            }, status=400)

    except PermissionDenied:
        logger.warning(f"[Payment] Permission denied: user={request.user.id}, order={order_id}")
        return JsonResponse({'success': False, 'error_message': 'Permission denied'}, status=403)

    except Exception as e:
        logger.exception("Payment processing failed unexpectedly.")
        if not settings.DEBUG:
            mail_admins(
                subject="Payment Processing Error",
                message=f"User: {request.user.email}\nOrder ID: {order_id}\nError: {str(e)}"
            )
        return JsonResponse({
            'success': False,
            'error_message': 'Internal server error. Please try again later.'
        }, status=500)


def capture_paypal_payment(order_id):
    try:
        access_token = get_paypal_access_token()
        capture_url = f"https://api-m.sandbox.paypal.com/v2/checkout/orders/{order_id}/capture"
        response = requests.post(
            capture_url,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {access_token}"
            }
        )

        if response.status_code == 201:
            return {'success': True, 'data': response.json()}
        else:
            error_msg = response.json().get('message', 'PayPal capture failed')
            return {'success': False, 'error': error_msg}

    except Exception as e:
        logger.exception("PayPal capture error")
        return {'success': False, 'error': str(e)}

def paypal_return(request):
    token = request.GET.get('token')
    payer_id = request.GET.get('PayerID')
    if token and payer_id:
        # Capture payment and process order
        return redirect('payment_success')
    return redirect('payment_failed')




def process_stripe_payment(request, order, payment, data):
    """
    Process a Stripe payment by retrieving and verifying an existing PaymentIntent.
    """
    # The frontend confirms the payment and sends us the ID.
    payment_intent_id = data.get('stripe_payment_intent_id')

    if not payment_intent_id:
        return JsonResponse({
            'success': False,
            'error_message': 'Payment Intent ID was not provided.'
        }, status=400)

    try:
        # Retrieve the PaymentIntent from Stripe's API to check its status.
        intent = stripe.PaymentIntent.retrieve(payment_intent_id)

        # --- Verification Step ---
        # Ensure the payment details from Stripe match your database records.
        expected_amount_cents = int(payment.amount * 100)
        if intent.amount_received != expected_amount_cents or intent.currency != payment.currency.lower():
            logger.error(
                f"Amount mismatch for Order {order.id}. "
                f"Expected: {expected_amount_cents} {payment.currency.lower()}. "
                f"Got: {intent.amount_received} {intent.currency}."
            )
            # You might want to automatically issue a refund here
            # stripe.Refund.create(payment_intent=intent.id)
            return JsonResponse({
                'success': False,
                'error_message': 'Payment amount does not match order total. Please contact support.'
            }, status=400)


        # --- Status Check ---
        if intent.status == 'succeeded':
            # The payment is successful and verified. Fulfill the order.
            payment.status = 'COMPLETED'
            payment.paid_at = timezone.now()
            payment.payment_method = 'card'
            payment.transaction_id = intent.id
            payment.save()

            order.status = 'PAID'
            order.save()

            PaymentLog.objects.create(
                payment=payment,
                log_type='SUCCESS',
                details={'method': 'stripe', 'intent_id': intent.id, 'status': intent.status}
            )

            redirect_url = reverse('payment:payment-complete', kwargs={'pk': order.id})
            return JsonResponse({'success': True, 'redirect_url': redirect_url})
        else:
            # The payment was not successful for another reason.
            PaymentLog.objects.create(
                payment=payment,
                log_type='FAILED',
                details={'method': 'stripe', 'intent_id': intent.id, 'status': intent.status}
            )
            return JsonResponse({
                'success': False,
                'error_message': 'Payment confirmation failed. Please try again.'
            }, status=400)

    except stripe.error.StripeError as e:
        logger.error(f"Stripe API error while processing {payment_intent_id}: {str(e)}")
        PaymentLog.objects.create(payment=payment, log_type='FAILED', details={'error_message': str(e)})
        return JsonResponse({'success': False, 'error_message': str(e)}, status=400)
    except Exception as e:
        logger.exception(f"A general error occurred in process_stripe_payment for order {order.id}")
        return JsonResponse({'success': False, 'error_message': 'An internal server error occurred.'}, status=500)


@method_decorator(login_required, name='dispatch')
class PaymentMethodCreateView(CreateView):
    model = PaymentMethod
    form_class = PaymentMethodForm
    template_name = 'payment/payment_form.html'
    success_url = reverse_lazy('payment:payment_methods')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.instance.user = self.request.user
        if form.cleaned_data.get('is_default'):
            PaymentMethod.objects.filter(user=self.request.user).update(is_default=False)
        messages.success(self.request, 'Payment method added successfully')
        return super().form_valid(form)


@method_decorator(login_required, name='dispatch')
class PaymentMethodUpdateView(UpdateView):
    model = PaymentMethod
    form_class = PaymentMethodForm
    template_name = 'payment/payment_form.html'
    success_url = reverse_lazy('payment:payment_methods')

    def get_queryset(self):
        return PaymentMethod.objects.filter(user=self.request.user)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        if form.cleaned_data.get('is_default'):
            PaymentMethod.objects.filter(user=self.request.user).exclude(pk=self.object.pk).update(is_default=False)
        messages.success(self.request, 'Payment method updated successfully')
        return super().form_valid(form)


@method_decorator(login_required, name='dispatch')
class PaymentMethodDeleteView(DeleteView):
    model = PaymentMethod
    success_url = reverse_lazy('payment:payment_methods')
    template_name = 'payment/payment_confirm_delete.html'

    def get_queryset(self):
        return PaymentMethod.objects.filter(user=self.request.user)

    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Payment method deleted successfully')
        return super().delete(request, *args, **kwargs)


@login_required
def set_default_payment(request, pk):
    payment = PaymentMethod.objects.get(pk=pk, user=request.user)
    PaymentMethod.objects.filter(user=request.user).update(is_default=False)
    payment.is_default = True
    payment.save()
    messages.success(request, 'Default payment method updated successfully')
    return redirect('payment:payment_methods')


@login_required
def payment_methods(request):
    return render(request, 'payment/payment_methods.html', {
        'payment_methods': PaymentMethod.objects.filter(user=request.user)
    })


class PaymentPendingView(DetailView):
    model = Order
    template_name = 'payment/payment_pending.html'
    context_object_name = 'order'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        order = self.object
        context['payment'] = order.order_payment
        context['payment_window'] = settings.PAYMENT_SETTINGS.get('PAYMENT_WINDOW_HOURS', 48)
        return context


class CashPaymentCompleteView(DetailView):
    model = Order
    template_name = 'payment/payment_complete.html'

    @transaction.atomic
    def get(self, request, *args, **kwargs):
        order = self.get_object()
        payment = order.order_payment

        if payment.status == 'COMPLETED':
            messages.warning(request, "Payment already completed")
            return redirect('payment:payment-status', pk=order.pk)

        payment.mark_as_paid()
        messages.success(request, "Cash payment confirmed successfully")
        return super().get(request, *args, **kwargs)


class MobileMoneyVerifyView(FormView):
    form_class = MobileMoneyVerificationForm
    template_name = 'payment/mobile_money_verify.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['order'] = get_object_or_404(Order, pk=self.kwargs['pk'])
        return context

    @transaction.atomic
    def form_valid(self, form):
        order = get_object_or_404(Order, pk=self.kwargs['pk'])
        payment = order.order_payment
        code = form.cleaned_data['verification_code']

        if payment.status == 'COMPLETED':
            messages.warning(self.request, "Payment already completed")
            return redirect('payment:payment-status', pk=order.pk)

        if not payment.verify_code(code):
            messages.error(self.request, "Invalid verification code")
            return self.form_invalid(form)

        payment.mark_as_paid()
        messages.success(self.request, "Mobile payment verified successfully")
        return redirect('payment:payment-complete', pk=order.pk)


class PaymentCompleteView(DetailView):
    model = Order
    template_name = 'payment/payment_complete.html'
    context_object_name = 'order'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['payment'] = self.object.payment  # Add payment to context
        return context


def mobile_money_verification(request, payment_id):
    payment = get_object_or_404(Payment, id=payment_id)

    if not payment.is_active:
        messages.error(request, "This payment link has expired")
        return redirect('payment:payment-expired')

    if request.method == 'POST':
        form = MobileMoneyVerificationForm(request.POST)
        if form.is_valid():
            if payment.verify_code(form.cleaned_data['verification_code']):
                return redirect('payment:payment-complete', pk=payment.order.pk)
            messages.error(request, "Invalid verification code")
    else:
        form = MobileMoneyVerificationForm()

    return render(request, 'payment/verify.html', {
        'form': form,
        'payment': payment,
        'expires_in': payment.time_remaining
    })


class ProcessPaymentView(View):
    def post(self, request, order_id):
        order = get_object_or_404(Order, id=order_id, user=request.user)
        payment = order.order_payment

        # Get payment method
        payment_method_id = request.POST.get('payment_method')
        payment_method = get_object_or_404(PaymentMethod, id=payment_method_id, user=request.user)

        # Update payment with selected method
        payment.payment_method = payment_method
        payment.method = payment_method.method_type
        payment.save()

        # Process payment based on method
        processor = PaymentProcessor(payment)
        result = processor.process()

        if result['success']:
            return JsonResponse({
                'success': True,
                'redirect_url': reverse('payment:payment-complete', kwargs={'pk': order.id})
            })
        else:
            payment.mark_as_failed(
                error_code=result.get('error_code'),
                error_message=result.get('error_message')
            )
            return JsonResponse({
                'success': False,
                'error': result.get('error_message', 'Payment failed')
            })


@method_decorator(login_required, name='dispatch')
class PayPalPaymentView(FormView):
    form_class = PayPalPaymentForm
    template_name = 'payment/paypal_payment.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['order'] = get_object_or_404(Order, id=self.kwargs['order_id'])
        return context

    def form_valid(self, form):
        order = get_object_or_404(Order, id=self.kwargs['order_id'])
        email = form.cleaned_data['email']
        save_method = form.cleaned_data['save_method']

        # Create or get PayPal payment method
        if save_method:
            payment_method, created = PaymentMethod.objects.get_or_create(
                user=self.request.user,
                method_type='PAYPAL',
                paypal_email=email,
                defaults={'is_default': True}
            )

            if not created:
                payment_method.is_default = True
                payment_method.save()

        # Process PayPal payment
        processor = PaymentProcessor(order.order_payment)
        result = processor.process_paypal(email)

        if result['success']:
            return redirect('payment:payment-complete', pk=order.id)
        else:
            messages.error(self.request, result['error_message'])
            return self.form_invalid(form)


def get_fallback_rate(from_curr, to_curr):
    pass



def get_live_exchange_rate(from_curr, to_curr):
    """Fetch live rates from external API with access key support"""
    try:
        # Use a real exchange rate API with access key
        params = {
            'base': from_curr,
            'symbols': to_curr,
        }

        # Add access key if configured
        if hasattr(settings, 'EXCHANGERATE_API_KEY'):
            params['access_key'] = settings.EXCHANGERATE_API_KEY

        response = requests.get(
            "https://api.exchangerate.host/latest",
            params=params,
            timeout=3
        )
        response.raise_for_status()
        data = response.json()

        if data.get('success', True):  # Some APIs don't have 'success' field
            return data['rates'].get(to_curr)
        else:
            error_msg = data.get('error', {}).get('info', 'API error')
            logger.error(f"Exchange rate API error: {error_msg}")
            return None
    except Exception as e:
        logger.error(f"Exchange rate API exception: {str(e)}")
        return None


@require_GET
def currency_convert(request):
    from_curr = request.GET.get('from')
    to_curr = request.GET.get('to')
    amount = request.GET.get('amount', 1)

    if not (from_curr and to_curr):
        return JsonResponse({'error': 'Missing parameters'}, status=400)

    try:
        # Use the shared exchange rate function
        rate = get_exchange_rate(from_curr, to_curr)
        if rate is None:
            # Use fallback rates
            fallback_rates = getattr(settings, 'CURRENCY_FALLBACK_RATES', {})
            rate_key = f"{from_curr}_{to_curr}"
            if rate_key in fallback_rates:
                rate = fallback_rates[rate_key]
            else:
                return JsonResponse({'error': 'Exchange rate not available'}, status=400)

        converted = Decimal(amount) * rate

        return JsonResponse({
            'rate': float(rate),
            'amount': float(converted),
            'from_currency': from_curr,
            'to_currency': to_curr,
            'original_amount': float(amount)
        })

    except Exception as e:
        logger.error(f"Currency conversion error: {str(e)}")
        return JsonResponse({'error': str(e)}, status=400)

class PaymentExpiredView(TemplateView):
    template_name = 'payment/expired.html'

@csrf_exempt
def paypal_success(request):
    token = request.GET.get('token')
    if not token:
        return HttpResponse("Missing token", status=400)

    # Capture payment
    access_token = get_paypal_access_token()
    capture_url = f"https://api-m.sandbox.paypal.com/v2/checkout/orders/{token}/capture"
    response = requests.post(
        capture_url,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}"
        }
    )
    data = response.json()

    if response.status_code == 201:
        return HttpResponse(f"Payment successful! Data: {data}")
    else:
        return HttpResponse(f"Capture failed! Error: {data}", status=400)

def paypal_cancel(request):
    return HttpResponse("Payment cancelled.")

def get_paypal_access_token():
    from requests.auth import HTTPBasicAuth
    auth = HTTPBasicAuth(settings.PAYPAL_CLIENT_ID, settings.PAYPAL_SECRET)
    response = requests.post(
        'https://api-m.sandbox.paypal.com/v1/oauth2/token',
        headers={"Accept": "application/json", "Accept-Language": "en_US"},
        data={'grant_type': 'client_credentials'},
        auth=auth
    )
    return response.json()['access_token']