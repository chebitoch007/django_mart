from django.views.generic import DetailView, FormView, TemplateView
from django.shortcuts import redirect, get_object_or_404, render
from django.contrib import messages
from django.db import transaction
from django.conf import settings
from .models import Payment
from orders.models import Order
from .forms import MobileMoneyVerificationForm

from django.views.generic import CreateView, UpdateView, DeleteView
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from django.urls import reverse_lazy
from django.contrib import messages
from .models import PaymentMethod
from .forms import PaymentMethodForm


@method_decorator(login_required, name='dispatch')
class PaymentMethodCreateView(CreateView):
    model = PaymentMethod
    form_class = PaymentMethodForm
    template_name = 'payment/payment_form.html'
    success_url = reverse_lazy('payment:payment_methods')

    def form_valid(self, form):
        form.instance.user = self.request.user
        if form.cleaned_data.get('is_default'):
            # Unset other default payment methods
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

    def form_valid(self, form):
        if form.cleaned_data.get('is_default'):
            # Unset other default payment methods
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