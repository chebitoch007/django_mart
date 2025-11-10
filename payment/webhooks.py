# payment/webhooks.py

from django.utils import timezone
from datetime import timedelta
from django.core.exceptions import ValidationError
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


def process_mpesa_webhook_data(payment, data):
    """
    ✅ FIXED: Processes M-Pesa webhook with idempotency - safe to call multiple times
    """
    try:
        stk_callback = data.get('Body', {}).get('stkCallback', {})
        result_code = stk_callback.get('ResultCode')
        callback_metadata = stk_callback.get('CallbackMetadata', {}) or {}
        items = callback_metadata.get('Item', [])

        # ✅ FIX: Skip if already completed
        if payment.status == 'COMPLETED':
            logger.info(f"Payment {payment.id} already COMPLETED, skipping webhook processing")
            return

        if result_code == 0:  # ✅ SUCCESS
            payment.status = 'COMPLETED'

            # Extract metadata safely
            for item in items:
                name = item.get('Name')
                value = item.get('Value')
                if name == 'MpesaReceiptNumber':
                    payment.transaction_id = value
                elif name == 'PhoneNumber':
                    payment.phone_number = str(value)
                elif name == 'Amount':
                    payment.amount = value

            payment.save(update_fields=['status', 'transaction_id', 'phone_number', 'amount'])

            # ✅ FIX: Handle already-paid orders gracefully
            try:
                order = payment.order

                # Only mark as paid if still pending
                if order.status == 'PENDING':
                    order.mark_as_paid(payment_method='MPESA')
                    logger.info(f"Order {order.id} marked as PAID after M-Pesa success")
                    clear_cart_after_payment(order)
                else:
                    logger.info(f"Order {order.id} already in {order.status} status, skipping mark_as_paid")

            except ValidationError as e:
                logger.error(f"Validation error for order {order.id}: {e}")
                payment.status = 'FAILED'
                payment.failure_type = 'STOCK_ISSUE'
                payment.save()
            except PermissionError as e:
                # Order was already processed by another thread/webhook
                logger.warning(f"Order {order.id} already processed (race condition): {e}")
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


@csrf_exempt
@require_http_methods(["POST", "GET"])
def handle_mpesa_webhook(request):
    """
    ✅ PRODUCTION-READY: Idempotent M-Pesa webhook handler
    """
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

        # ✅ Use atomic transaction with SELECT FOR UPDATE
        with transaction.atomic():
            # Lock the payment record
            payment = (
                Payment.objects
                .select_for_update(nowait=False)
                .filter(checkout_request_id=checkout_request_id)
                .first()
            )

            if not payment:
                logger.error(f"No Payment found with CheckoutRequestID={checkout_request_id}")
                return JsonResponse({'error': 'Payment not found'}, status=404)

            # ✅ IDEMPOTENCY CHECK: Skip if already completed
            if payment.status == 'COMPLETED':
                logger.info(f"Payment {payment.id} already COMPLETED (idempotent)")
                return JsonResponse({'status': 'already_processed', 'payment_id': payment.id})

            # ✅ Check processing lock (with timeout)
            if payment.processing_locked:
                lock_age = timezone.now() - payment.locked_at if payment.locked_at else timedelta(0)
                if lock_age < timedelta(minutes=5):
                    logger.info(f"Payment {payment.id} is locked (age: {lock_age})")
                    return JsonResponse({'status': 'processing', 'message': 'Payment currently processing'})
                else:
                    # Release stale lock
                    logger.warning(f"Releasing stale lock on payment {payment.id}")
                    payment.release_lock()

            # ✅ Mark as processing to prevent race conditions
            payment.mark_processing()

            # Store raw callback
            payment.raw_response = data
            payment.result_code = str(result_code)
            payment.result_description = stk_callback.get('ResultDesc', '')
            payment.save(update_fields=['raw_response', 'result_code', 'result_description'])

            # Process based on result code
            try:
                if result_code == 0:  # SUCCESS
                    process_successful_payment(payment, stk_callback)
                elif result_code == 1032:  # USER CANCELLED
                    payment.status = 'FAILED'
                    payment.failure_type = 'USER_CANCELLED'
                    payment.save(update_fields=['status', 'failure_type'])
                elif result_code in [1, 2, 3, 4, 5, 8, 1031]:  # TEMPORARY
                    payment.status = 'FAILED'
                    payment.failure_type = 'TEMPORARY'
                    payment.save(update_fields=['status', 'failure_type'])
                else:  # PERMANENT
                    payment.status = 'FAILED'
                    payment.failure_type = 'PERMANENT'
                    payment.save(update_fields=['status', 'failure_type'])
            finally:
                # ✅ Always release lock
                payment.release_lock()

        return JsonResponse({'status': 'success', 'payment_id': payment.id})

    except json.JSONDecodeError:
        logger.error("Invalid JSON body in M-Pesa webhook")
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        logger.exception("Error processing M-Pesa webhook")
        return JsonResponse({'error': str(e)}, status=500)

def process_successful_payment(payment, stk_callback):
    """
    ✅ Process successful M-Pesa payment with proper error handling
    """
    callback_metadata = stk_callback.get('CallbackMetadata', {}) or {}
    items = callback_metadata.get('Item', [])

    # Extract metadata
    for item in items:
        name = item.get('Name')
        value = item.get('Value')
        if name == 'MpesaReceiptNumber':
            payment.transaction_id = value
        elif name == 'PhoneNumber':
            payment.phone_number = str(value)
        elif name == 'Amount':
            payment.amount = value

    payment.status = 'COMPLETED'
    payment.save(update_fields=['status', 'transaction_id', 'phone_number', 'amount'])

    # Update order
    try:
        order = payment.order
        if order.status == 'PENDING':
            order.mark_as_paid(payment_method='MPESA')
            clear_cart_after_payment(order)
            logger.info(f"✅ Order {order.id} marked as PAID via webhook")
    except ValidationError as e:
        logger.error(f"Validation error for order {order.id}: {e}")
        payment.status = 'FAILED'
        payment.failure_type = 'STOCK_ISSUE'
        payment.save(update_fields=['status', 'failure_type'])
        raise
    except PermissionError as e:
        logger.warning(f"Order {order.id} already processed: {e}")
    except Exception as e:
        logger.error(f"Error updating order: {e}")
        raise


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
        transmission_id = request.META.get('HTTP_PAYPAL_TRANSMISSION_ID')
        transmission_time = request.META.get('HTTP_PAYPAL_TRANSMISSION_TIME')
        transmission_sig = request.META.get('HTTP_PAYPAL_TRANSMISSION_SIG')
        cert_url = request.META.get('HTTP_PAYPAL_CERT_URL')
        auth_algo = request.META.get('HTTP_PAYPAL_AUTH_ALGO')

        if not all([transmission_id, transmission_time, transmission_sig, cert_url, auth_algo]):
            logger.warning("Missing PayPal webhook verification headers")
            return False

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
        return True  # Placeholder for actual implementation
    except Exception as e:
        logger.error(f"PayPal webhook API verification failed: {str(e)}")
        return False


def handle_payment_capture_completed(resource):
    """
    ✅ FIXED: Handle completed PayPal payment with idempotency
    """
    try:
        capture_id = resource.get('id')
        order_id = None
        purchase_units = resource.get('purchase_units', [{}])

        for unit in purchase_units:
            custom_id = unit.get('custom_id')
            if custom_id:
                order_id = custom_id
                break
            invoice_id = unit.get('invoice_id')
            if invoice_id and invoice_id.startswith('ORDER_'):
                order_id = invoice_id.replace('ORDER_', '')
                break

        if not order_id and resource.get('custom_id'):
            order_id = resource.get('custom_id')

        if not order_id:
            logger.error(f"No order ID found in PayPal webhook. Capture: {capture_id}")
            return JsonResponse({'error': 'Missing order ID'}, status=400)

        if order_id.startswith('ORDER_'):
            order_id = order_id.replace('ORDER_', '')

        logger.info(f"Processing PayPal payment completion for order {order_id}, capture: {capture_id}")

        try:
            payment = Payment.objects.get(order_id=order_id, provider='PAYPAL')

            with transaction.atomic():
                payment = Payment.objects.select_for_update().get(
                    order_id=order_id,
                    provider='PAYPAL'
                )

                # ✅ FIX: Skip if already completed
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

                # ✅ FIX: Handle already-paid orders
                order = payment.order
                try:
                    if order.status == 'PENDING':
                        order.mark_as_paid(payment_method='PAYPAL')
                        logger.info(f"Order {order.id} marked as PAID via PayPal webhook")
                        clear_cart_after_payment(order)
                    else:
                        logger.info(f"Order {order.id} already in {order.status} status")

                except ValidationError as e:
                    logger.error(f"Validation error for order {order.id}: {e}")
                    payment.status = 'FAILED'
                    payment.failure_type = 'STOCK_ISSUE'
                    payment.save()
                except PermissionError as e:
                    logger.warning(f"Order {order.id} already processed: {e}")

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
        result = paypal_client._make_request('GET', f'/v2/payments/captures/{capture_id}')
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
        logger.info(f"PayPal payment refunded: {refund_id} for capture {capture_id}")

        payments = Payment.objects.filter(transaction_id=capture_id, provider='PAYPAL')
        if payments.exists():
            payment = payments.first()
            payment.status = 'REFUNDED'
            payment.save()

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