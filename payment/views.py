from decimal import Decimal

import requests
from django.views.decorators.csrf import csrf_exempt

from .models import PaymentLog
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.views.generic import DetailView, FormView, TemplateView, View, DeleteView, UpdateView, CreateView
from django.shortcuts import redirect, get_object_or_404, render
from django.contrib import messages
from django.db import transaction
from django.conf import settings
from django.urls import reverse
from django.http import JsonResponse
from .models import Payment, PaymentMethod
from orders.models import Order
from .forms import MobileMoneyVerificationForm, PaymentMethodForm, PayPalPaymentForm
from django.views.decorators.http import require_GET
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from django.urls import reverse_lazy
from .services import PaymentProcessor, convert_currency
from django.views.decorators.http import require_POST
from .forms import PaymentProcessingForm
import logging
from core.utils import get_exchange_rate

logger = logging.getLogger(__name__)


from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.shortcuts import reverse
import logging

logger = logging.getLogger(__name__)

@csrf_protect
@csrf_protect
@require_POST
@login_required
def process_payment(request):
    # Rate limiting implementation
    user_key = f"payment_attempts_{request.user.id}"
    attempts = cache.get(user_key, 0)

    if attempts >= 5:
        return JsonResponse({
            'success': False,
            'error_message': 'Too many attempts. Please try again later.'
        }, status=429)

    cache.set(user_key, attempts + 1, 300)  # 5 min window
    try:
        form = PaymentProcessingForm(request.POST, user=request.user)
        if not form.is_valid():
            error_msg = '; '.join(f"{k}: {v[0]}" for k, v in form.errors.items())
            return JsonResponse({'success': False, 'error_message': error_msg}, status=400)

        order = form.cleaned_data['order']
        payment=order.order_payment
        payment_method = form.cleaned_data['payment_method']

        # Validate method
        if payment_method not in ['mpesa', 'airtel', 'card', 'paypal']:
            return JsonResponse({'success': False, 'error_message': 'Invalid payment method'}, status=400)

        # Ensure order ownership
        if order.user != request.user:
            raise PermissionDenied("Order does not belong to this user")

        payment = order.order_payment  # Assumes Payment FK relation exists

        # Idempotency and duplicate prevention
        if payment.status != 'PENDING':
            PaymentLog.objects.create(
                payment=payment,
                log_type='FAILED',
                details={'reason': 'Duplicate attempt', 'user': request.user.id}
            )
            return JsonResponse({
                'success': False,
                'error_message': 'Order has already been processed'
            }, status=400)

        PaymentLog.objects.create(
            payment=payment,
            log_type='PROCESSING',
            details={
                'method': payment_method,
                'amount': form.cleaned_data['amount'],
                'currency': form.cleaned_data['currency']
            }
        )

        processor = PaymentProcessor(
            payment=payment,
            **form.cleaned_data
        )
        result = processor.process()

        if result.get('success'):
            PaymentLog.objects.create(
                payment=payment,
                log_type='SUCCESS',
                details={'gateway_response': result.get('gateway_data', {})}
            )
            if payment_method == 'paypal':
                url = reverse('payment:paypal_payment', args=[order.id])
            else:
                url = reverse('payment:payment_complete', kwargs={'pk': order.id})
            return JsonResponse({'success': True, 'redirect_url': url})
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
        logger.warning("Permission denied during payment processing")
        return JsonResponse({'success': False, 'error_message': 'Permission denied'}, status=403)
    except Exception as exc:
        logger.exception("Internal payment processing error")
        if not settings.DEBUG:
            from django.core.mail import mail_admins
            mail_admins("Payment Error", f"User: {request.user.email}\nError: {exc}")
        return JsonResponse({'success': False, 'error_message': 'Internal server error'}, status=500)




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
    try:
        # Use a real exchange rate API
        response = requests.get(
            f"https://api.exchangerate.host/latest?base={from_curr}&symbols={to_curr}",
            timeout=3
        )
        data = response.json()
        return data['rates'].get(to_curr)
    except Exception as e:
        logger.error(f"Exchange rate API error: {str(e)}")
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