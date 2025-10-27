#payment/webhooks.py
from .cart_utils import clear_cart_after_payment
import json
import requests
from django.conf import settings
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from core.utils import logger
from .models import Payment
from django.views.decorators.http import require_http_methods

from .utils import paypal_client




def get_cart_for_user(user):
    """Safely get cart for user"""
    from cart.models import Cart
    try:
        return Cart.objects.get(user=user)
    except Cart.DoesNotExist:
        return None
    except Cart.MultipleObjectsReturned:
        # Handle multiple carts by using the most recent
        return Cart.objects.filter(user=user).order_by('-created_at').first()




@csrf_exempt
@require_http_methods(["POST", "GET"])
def handle_mpesa_webhook(request):
    """Handles M-Pesa webhook callbacks with cart clearing, duplicate prevention, and atomic updates."""

    if request.method == "GET":
        return JsonResponse({'status': 'ok', 'message': 'M-Pesa webhook is active'})

    logger.info("M-Pesa webhook received")

    try:
        if not request.body:
            return JsonResponse({'error': 'Empty body'}, status=400)

        data = json.loads(request.body)
        stk_callback = data.get('Body', {}).get('stkCallback', {})
        result_code = stk_callback.get('ResultCode')
        checkout_request_id = stk_callback.get('CheckoutRequestID')

        if not checkout_request_id:
            return JsonResponse({'error': 'Missing CheckoutRequestID'}, status=400)

        with transaction.atomic():
            payments = Payment.objects.filter(
                checkout_request_id=checkout_request_id
            ).select_for_update().order_by('-created_at')

            if not payments.exists():
                logger.error(f"No Payment found with CheckoutRequestID={checkout_request_id}")
                return JsonResponse({'error': 'Payment not found'}, status=404)

            payment = payments.first()
            if payments.count() > 1:
                logger.warning(f"Multiple payments found for {checkout_request_id}, keeping most recent")
                payments.exclude(id=payment.id).update(
                    status='FAILED',
                    failure_type='DUPLICATE',
                    result_description='Multiple payments detected, using most recent'
                )

            logger.info(f"Processing webhook for payment {payment.id}")

            # Store raw callback and update
            payment.raw_response = json.dumps(data)
            payment.result_code = result_code
            payment.result_description = stk_callback.get('ResultDesc', '')

            # Process using helper function
            process_mpesa_webhook_data(payment, data)

        return JsonResponse({'status': 'success'})

    except json.JSONDecodeError:
        logger.error("Invalid JSON body in M-Pesa webhook")
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        logger.exception("Error processing M-Pesa webhook")
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def handle_paypal_webhook(request):
    """Enhanced PayPal webhook handler with proper signature verification"""
    logger.info("PayPal webhook received")

    # Verify webhook signature
    if not verify_paypal_webhook(request):
        logger.warning("PayPal webhook signature verification failed")
        return JsonResponse({'error': 'Invalid signature'}, status=400)

    try:
        payload = json.loads(request.body)
        event_type = payload.get('event_type')
        resource = payload.get('resource', {})
        webhook_id = payload.get('id')

        logger.info(f"PayPal webhook event: {event_type}, ID: {webhook_id}")

        # Verify webhook with PayPal API (additional security)
        if not verify_webhook_with_paypal(payload):
            logger.error("PayPal webhook verification with API failed")
            return JsonResponse({'error': 'Webhook verification failed'}, status=400)

        # Handle different event types
        if event_type == 'PAYMENT.CAPTURE.COMPLETED':
            return handle_payment_capture_completed(resource)
        elif event_type == 'PAYMENT.CAPTURE.DENIED':
            return handle_payment_capture_denied(resource)
        elif event_type == 'PAYMENT.CAPTURE.PENDING':
            return handle_payment_capture_pending(resource)
        elif event_type == 'CHECKOUT.ORDER.APPROVED':
            return handle_checkout_order_approved(resource)
        elif event_type == 'CHECKOUT.ORDER.COMPLETED':
            return handle_checkout_order_completed(resource)
        elif event_type == 'PAYMENT.CAPTURE.REFUNDED':
            return handle_payment_refunded(resource)
        else:
            logger.info(f"Ignoring PayPal webhook event: {event_type}")
            return JsonResponse({'status': 'ignored'})

    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in PayPal webhook: {str(e)}")
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        logger.exception("Error processing PayPal webhook")
        return JsonResponse({'error': 'Internal server error'}, status=500)


def verify_paypal_webhook(request):
    """Proper PayPal webhook signature verification"""
    try:
        # Get required headers
        transmission_id = request.META.get('HTTP_PAYPAL_TRANSMISSION_ID')
        transmission_time = request.META.get('HTTP_PAYPAL_TRANSMISSION_TIME')
        transmission_sig = request.META.get('HTTP_PAYPAL_TRANSMISSION_SIG')
        cert_url = request.META.get('HTTP_PAYPAL_CERT_URL')
        auth_algo = request.META.get('HTTP_PAYPAL_AUTH_ALGO')

        if not all([transmission_id, transmission_time, transmission_sig, cert_url, auth_algo]):
            logger.warning("Missing PayPal webhook verification headers")
            return False

        # Verify webhook signature using PayPal's API
        verification_url = f"{settings.PAYPAL_API_URL}/v1/notifications/verify-webhook-signature"

        verification_data = {
            "transmission_id": transmission_id,
            "transmission_time": transmission_time,
            "transmission_sig": transmission_sig,
            "cert_url": cert_url,
            "auth_algo": auth_algo,
            "webhook_id": settings.PAYPAL_WEBHOOK_ID,
            "webhook_event": json.loads(request.body)
        }

        access_token = paypal_client._get_access_token()
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {access_token}'
        }

        response = requests.post(verification_url, json=verification_data, headers=headers, timeout=10)

        if response.status_code == 200:
            result = response.json()
            return result.get('verification_status') == 'SUCCESS'

        logger.error(f"PayPal webhook verification failed: {response.status_code}")
        return False

    except Exception as e:
        logger.error(f"Webhook verification error: {str(e)}")
        return False


def verify_webhook_with_paypal(payload):
    """Additional verification by calling PayPal API"""
    try:
        webhook_id = payload.get('id')
        if not webhook_id:
            return False

        # In production, implement PayPal webhook verification API call
        # This ensures the webhook is genuinely from PayPal
        return True  # Placeholder for actual implementation

    except Exception as e:
        logger.error(f"PayPal webhook API verification failed: {str(e)}")
        return False


def handle_payment_capture_completed(resource):
    """Handle completed PayPal payment capture with proper order ID extraction"""
    try:
        capture_id = resource.get('id')

        # Extract order ID from multiple possible locations
        order_id = None
        purchase_units = resource.get('purchase_units', [{}])

        for unit in purchase_units:
            # Try custom_id first
            custom_id = unit.get('custom_id')
            if custom_id:
                order_id = custom_id
                break

            # Try invoice_id as fallback
            invoice_id = unit.get('invoice_id')
            if invoice_id and invoice_id.startswith('ORDER_'):
                order_id = invoice_id.replace('ORDER_', '')
                break

        # Also check resource level
        if not order_id and resource.get('custom_id'):
            order_id = resource.get('custom_id')

        if not order_id:
            logger.error(f"No order ID found in PayPal webhook. Capture: {capture_id}")
            return JsonResponse({'error': 'Missing order ID'}, status=400)

        # Remove ORDER_ prefix if present
        if order_id.startswith('ORDER_'):
            order_id = order_id.replace('ORDER_', '')

        logger.info(f"Processing PayPal payment completion for order {order_id}, capture: {capture_id}")

        try:
            payment = Payment.objects.get(order_id=order_id, provider='PAYPAL')

            # Prevent duplicate processing with transaction lock
            with transaction.atomic():
                payment = Payment.objects.select_for_update().get(
                    order_id=order_id,
                    provider='PAYPAL'
                )

                if payment.status == 'COMPLETED':
                    logger.info(f"Payment already completed for order {order_id}")
                    return JsonResponse({'status': 'already_processed'})

                # Verify capture status with PayPal API
                capture_details = verify_capture_status(capture_id)
                if not capture_details or capture_details.get('status') != 'COMPLETED':
                    logger.error(f"Capture verification failed for {capture_id}")
                    return JsonResponse({'error': 'Capture verification failed'}, status=400)

                # Update payment status
                payment.status = 'COMPLETED'
                payment.transaction_id = capture_id
                payment.raw_response = resource
                payment.save()

                # ✅ FIXED: Use the order model's method
                order = payment.order
                try:
                    order.mark_as_paid(payment_method='PAYPAL')
                    logger.info(f"Order {order.id} marked as PAID via model method.")
                    clear_cart_after_payment(order)
                except ValidationError as e:
                    logger.error(f"Stock error marking order {order.id} as paid: {e}")
                    # Handle this business logic error (e.g., set status to 'FAILED')
                    payment.status = 'FAILED'
                    payment.failure_type = 'STOCK_ISSUE'
                    payment.save()

                logger.info(f"PayPal payment completed for order {order_id}")
                return JsonResponse({'status': 'success'})

        except Payment.DoesNotExist:
            logger.error(f"Payment not found for order {order_id}")
            return JsonResponse({'error': 'Payment not found'}, status=404)

    except Exception as e:
        logger.exception("Error handling payment capture completion")
        return JsonResponse({'error': 'Processing failed'}, status=500)


def verify_capture_status(capture_id):
    """Verify capture status with PayPal API"""
    try:
        from .utils import paypal_client
        result = paypal_client._make_request(
            'GET',
            f'/v2/payments/captures/{capture_id}'
        )
        return result
    except Exception as e:
        logger.error(f"Capture verification failed: {str(e)}")
        return None

def handle_payment_capture_denied(resource):
    """Handle denied PayPal payment capture"""
    try:
        capture_id = resource.get('id')
        order_id = resource.get('custom_id')

        if order_id and order_id.startswith('ORDER_'):
            order_id = order_id.replace('ORDER_', '')

        logger.warning(f"PayPal payment denied for order {order_id}, capture: {capture_id}")

        if order_id:
            try:
                payment = Payment.objects.get(order_id=order_id, provider='PAYPAL')
                payment.status = 'FAILED'
                payment.failure_type = 'PAYPAL_DENIED'
                payment.result_description = resource.get('details', {}).get('description', 'Payment denied')
                payment.save()

                logger.info(f"Updated payment status to FAILED for order {order_id}")
            except Payment.DoesNotExist:
                logger.error(f"Payment not found for denied order {order_id}")

        return JsonResponse({'status': 'processed'})

    except Exception as e:
        logger.exception("Error handling payment capture denial")
        return JsonResponse({'error': 'Processing failed'}, status=500)


def handle_payment_refunded(resource):
    """Handle refunded PayPal payments"""
    try:
        refund_id = resource.get('id')
        capture_id = resource.get('capture_id')
        amount = resource.get('amount', {})

        logger.info(f"PayPal payment refunded: {refund_id} for capture {capture_id}")

        # Find payment by capture ID
        payments = Payment.objects.filter(transaction_id=capture_id, provider='PAYPAL')
        if payments.exists():
            payment = payments.first()
            payment.status = 'REFUNDED'
            payment.save()

            # Update order status
            order = payment.order
            order.status = 'REFUNDED'
            order.save()

            logger.info(f"Order {order.id} marked as REFUNDED")

        return JsonResponse({'status': 'processed'})

    except Exception as e:
        logger.exception("Error handling payment refund")
        return JsonResponse({'error': 'Processing failed'}, status=500)


def handle_payment_capture_pending(resource):
    """Handle pending PayPal payment capture"""
    logger.info(f"PayPal payment pending: {resource.get('id')}")
    return JsonResponse({'status': 'processed'})


def handle_checkout_order_approved(resource):
    """Handle approved checkout order"""
    logger.info(f"PayPal checkout order approved: {resource.get('id')}")
    return JsonResponse({'status': 'processed'})


def handle_checkout_order_completed(resource):
    """Handle completed checkout order"""
    logger.info(f"PayPal checkout order completed: {resource.get('id')}")
    return JsonResponse({'status': 'processed'})


def send_payment_confirmation(order, payment):
    """Send payment confirmation email (implement as needed)"""
    try:
        # Implement email sending logic here
        logger.info(f"Payment confirmation would be sent for order {order.id}")
        pass
    except Exception as e:
        logger.error(f"Failed to send payment confirmation: {str(e)}")

def process_mpesa_webhook_data(payment, data):
    """Processes a stored M-Pesa webhook payload and updates payment/order state accordingly."""
    try:
        stk_callback = data.get('Body', {}).get('stkCallback', {})
        result_code = stk_callback.get('ResultCode')
        callback_metadata = stk_callback.get('CallbackMetadata', {}) or {}
        items = callback_metadata.get('Item', [])

        if result_code == 0:  # ✅ SUCCESS
            payment.status = 'COMPLETED'
            # ... (set transaction_id, phone, amount)
            payment.save(...)

            # ✅ FIXED: Use the order model's method
            try:
                order = payment.order
                order.mark_as_paid(payment_method='MPESA')
                logger.info(f"Order {order.id} marked as PAID after M-Pesa success")
                clear_cart_after_payment(order)
            except ValidationError as e:
                logger.error(f"Stock error marking order {order.id} as paid (M-Pesa): {e}")
                payment.status = 'FAILED'
                payment.failure_type = 'STOCK_ISSUE'
                payment.save()
            except Exception as e:
                logger.error(f"Error updating order after M-Pesa success: {e}")


        elif result_code == 1032:  # ❌ User cancelled
            payment.status = 'FAILED'
            payment.failure_type = 'USER_CANCELLED'
            payment.save(update_fields=['status', 'failure_type'])

        elif result_code in [1, 2, 3, 4, 5, 8, 1031]:  # ⚠️ Temporary failures
            payment.status = 'FAILED'
            payment.failure_type = 'TEMPORARY'
            payment.save(update_fields=['status', 'failure_type'])

        else:  # 🛑 Permanent or unknown failure
            payment.status = 'FAILED'
            payment.failure_type = 'PERMANENT'
            payment.save(update_fields=['status', 'failure_type'])

    except Exception as e:
        logger.exception(f"Error processing stored M-Pesa webhook for payment {payment.id}: {e}")

