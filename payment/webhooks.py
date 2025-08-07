
import logging

from django.conf import settings
import hmac
import hashlib
import stripe
from django.http import JsonResponse, HttpResponse
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
def stripe_webhook(request):  # REMOVED THE PROBLEMATIC DECORATOR
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')

    if not sig_header:
        logger.warning("Stripe webhook: Missing signature header")
        return HttpResponse(status=400)

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError as e:
        logger.error(f"Invalid payload: {e}")
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError as e:
        logger.error(f"Signature verification failed: {e}")
        return HttpResponse(status=400)

    # Handle successful payment
    if event['type'] == 'payment_intent.succeeded':
        intent = event['data']['object']
        payment_id = intent.get('metadata', {}).get('payment_id')

        try:
            if payment_id:
                payment = Payment.objects.get(id=payment_id)
            else:
                payment = Payment.objects.get(gateway_transaction_id=intent['id'])

            # Mark payment as paid
            payment.mark_as_paid(transaction_id=intent['id'])
            return JsonResponse({'status': 'success'})

        except Payment.DoesNotExist:
            logger.error(f"Stripe webhook: Payment not found for intent {intent['id']} (payment_id={payment_id})")
            return JsonResponse({'status': 'payment not found'}, status=404)
        except Exception as e:
            logger.exception(f"Error processing Stripe webhook: {e}")
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

    # Other event types can be handled if needed
    return HttpResponse(status=200)

@csrf_exempt
def paypal_webhook(request):
    if request.method == "POST":
        payload = json.loads(request.body)

        # Log or process event here
        logging.info(f"Received PayPal webhook: {payload}")

        # TODO: Validate with PayPal and act accordingly

        return JsonResponse({'status': 'success'})
    return JsonResponse({'error': 'Invalid method'}, status=405)







