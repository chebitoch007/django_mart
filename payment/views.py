from django.views.generic import DetailView, FormView, TemplateView
from django.shortcuts import redirect, get_object_or_404, render
from django.contrib import messages
from django.db import transaction
from django.conf import settings
from .models import Payment
from orders.models import Order
from .forms import MobileMoneyVerificationForm


class PaymentPendingView(DetailView):
    model = Order
    template_name = 'payment/payment_pending.html'
    context_object_name = 'order'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        order = self.object
        context['payment'] = order.payment
        context['payment_window'] = settings.PAYMENT_SETTINGS.get('PAYMENT_WINDOW_HOURS', 48)
        return context


class CashPaymentCompleteView(DetailView):
    model = Order
    template_name = 'payment/payment_complete.html'

    @transaction.atomic
    def get(self, request, *args, **kwargs):
        order = self.get_object()
        payment = order.payment

        if payment.is_paid:
            messages.warning(request, "Payment already completed")
            return redirect('payment-status', pk=order.pk)

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
        payment = order.payment
        code = form.cleaned_data['verification_code']

        if payment.is_paid:
            messages.warning(self.request, "Payment already completed")
            return redirect('payment-status', pk=order.pk)

        if not payment.verify_code(code):
            messages.error(self.request, "Invalid verification code")
            return self.form_invalid(form)

        payment.mark_as_paid()
        messages.success(self.request, "Mobile payment verified successfully")
        return redirect('payment-complete', pk=order.pk)


class PaymentCompleteView(TemplateView):
    template_name = 'payment/payment_complete.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['order'] = get_object_or_404(Order, pk=self.kwargs['pk'])
        return context


def mobile_money_verification(request, payment_id):
    payment = get_object_or_404(Payment, id=payment_id)

    if not payment.is_active:
        messages.error(request, "This payment link has expired")
        return redirect('payment-expired')

    if request.method == 'POST':
        form = MobileMoneyVerificationForm(request.POST)
        if form.is_valid():
            if payment.verify_code(form.cleaned_data['verification_code']):
                return redirect('payment-complete', pk=payment.order.pk)
            messages.error(request, "Invalid verification code")
    else:
        form = MobileMoneyVerificationForm()

    return render(request, 'payment/verify.html', {
        'form': form,
        'payment': payment,
        'expires_in': payment.time_remaining
    })