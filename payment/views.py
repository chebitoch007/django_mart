import stripe
from django.conf import settings
from django.views.generic.base import TemplateView
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
from orders.models import Order

stripe.api_key = settings.STRIPE_SECRET_KEY


class PaymentView(TemplateView):
    template_name = 'payment/payment.html'

    def get_context_data(self, **kwargs):
        order = Order.objects.get(id=self.kwargs['order_id'])
        context = super().get_context_data(**kwargs)
        context['order'] = order
        context['stripe_publishable_key'] = settings.STRIPE_PUBLISHABLE_KEY
        return context


@csrf_exempt
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META['HTTP_STRIPE_SIGNATURE']
    event = None

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET)
    except ValueError as e:
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError as e:
        return HttpResponse(status=400)

    if event.type == 'checkout.session.completed':
        session = event.data.object
        if session.mode == 'payment' and session.payment_status == 'paid':
            try:
                order = Order.objects.get(id=session.client_reference_id)
                order.paid = True
                order.save()
            except Order.DoesNotExist:
                return HttpResponse(status=404)

    return HttpResponse(status=200)