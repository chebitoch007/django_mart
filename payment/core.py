from django.views.generic import TemplateView
from django.shortcuts import get_object_or_404
from orders.models import Order


class PaymentCheckoutView(TemplateView):
    template_name = 'payment/checkout.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        order = get_object_or_404(Order, id=self.kwargs['order_id'])

        context.update({
            'order': order,
            'methods': [
                {'name': 'M-Pesa', 'template': 'payment/methods/mpesa.html'},
                {'name': 'Airtel Money', 'template': 'payment/methods/airtel.html'},
                {'name': 'PesaLink', 'template': 'payment/methods/pesalink.html'}
            ]
        })
        return context