import hmac
import hashlib

import stripe
from django.http import JsonResponse, HttpResponse

from djangomart import settings


from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.http import JsonResponse

from .models import Payment, logger
from .security import WebhookSecurity
from .providers import PaymentProcessor
import json


class WebhookSecurity:
    @staticmethod
    def verify_signature(request, provider):
        """Verify webhook signature with provider-specific method"""
        secret = getattr(settings, f"{provider.upper()}_WEBHOOK_SECRET", None)
        if not secret:
            logger.error(f"No webhook secret for {provider}")
            return False

        # Get signature from header
        signature_header = request.headers.get('Stripe-Signature') if provider == 'stripe' \
            else request.headers.get('PayPal-Transmission-Sig') if provider == 'paypal' \
            else request.headers.get('X-Signature')

        if not signature_header:
            return False

        # Verify based on provider
        if provider == 'stripe':
            return WebhookSecurity.verify_stripe_signature(request.body, signature_header, secret)
        elif provider == 'paypal':
            return WebhookSecurity.verify_paypal_signature(request, secret)
        else:
            return WebhookSecurity.verify_generic_signature(request.body, signature_header, secret)

    @staticmethod
    def verify_stripe_signature(payload, signature, secret):
        try:
            event = stripe.Webhook.construct_event(
                payload, signature, secret
            )
            return True
        except stripe.error.SignatureVerificationError as e:
            logger.error(f"Stripe signature error: {str(e)}")
            return False

    @staticmethod
    def verify_paypal_signature(request, secret):
        # Actual implementation would verify PayPal transmission
        return True  # Simplified for example

    @staticmethod
    def verify_generic_signature(payload, signature, secret):
        expected_signature = hmac.new(
            secret.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(signature, expected_signature)


@csrf_exempt
@require_POST
def payment_webhook(request, provider):
    """Unified webhook handler for all providers"""
    # Verify webhook signature
    if not WebhookSecurity.verify_signature(request, provider):
        return HttpResponse(status=401)

    try:
        payload = json.loads(request.body)
        event_type = payload.get('type')

        # Handle payment_intent.succeeded (Stripe)
        if provider == 'stripe' and event_type == 'payment_intent.succeeded':
            payment_id = payload['data']['object']['metadata'].get('payment_id')
            if payment_id:
                payment = Payment.objects.get(id=payment_id)
                payment.mark_as_paid()
                return JsonResponse({'status': 'success'})

        # Handle M-Pesa callback
        elif provider == 'mpesa' and event_type == 'stk_callback':
            checkout_id = payload['Body']['stkCallback']['CheckoutRequestID']
            result_code = payload['Body']['stkCallback']['ResultCode']

            payment = Payment.objects.get(gateway_response__contains=checkout_id)
            if result_code == 0:
                payment.mark_as_paid()
            else:
                payment.mark_as_failed(
                    error_code='MPESA_FAILURE',
                    error_message=payload['Body']['stkCallback']['ResultDesc']
                )
            return JsonResponse({'status': 'processed'})

        # Handle PayPal webhooks
        elif provider == 'paypal' and event_type == 'PAYMENT.CAPTURE.COMPLETED':
            payment_id = payload['resource']['custom_id']
            payment = Payment.objects.get(id=payment_id)
            payment.mark_as_paid()
            return JsonResponse({'status': 'success'})

        return JsonResponse({'status': 'unhandled_event'}, status=200)

    except Payment.DoesNotExist:
        logger.error("Webhook error: Payment not found")
        return JsonResponse({'error': 'Payment not found'}, status=404)
    except Exception as e:
        logger.exception("Webhook processing failed")
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_POST
@WebhookSecurity.secure_webhook_view
def stripe_webhook(request):
    payload = json.loads(request.body)
    payment_id = payload['data']['object']['metadata'].get('payment_id')

    if not payment_id:
        return JsonResponse({'status': 'missing payment id'}, status=400)

    try:
        payment = Payment.objects.get(id=payment_id)
        processor = PaymentProcessor(payment)
        processor.provider.handle_webhook(payload)
        return JsonResponse({'status': 'success'})
    except Payment.DoesNotExist:
        return JsonResponse({'status': 'payment not found'}, status=404)







