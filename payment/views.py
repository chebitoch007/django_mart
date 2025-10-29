# payment/views.py
from django.core.exceptions import ValidationError
import requests
from django.conf import settings
from django.shortcuts import render, redirect
from django.urls import reverse
from .cart_utils import clear_cart_after_payment
from django.db import transaction
from datetime import timedelta
from django.utils import timezone
import json
from decimal import Decimal, ROUND_HALF_UP
from djmoney.money import Money
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.http import JsonResponse
import logging
from orders.models import Order
from .models import Payment
from .utils import (
    initiate_mpesa_payment,
    create_paypal_order,
    is_paypal_currency_supported
)
from .webhooks import (
    handle_mpesa_webhook,
    handle_paypal_webhook, process_mpesa_webhook_data
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------
# SAFE PAYMENT CREATION
# ---------------------------------------------------------
# payment/views.py

def get_or_create_payment_safe(order, provider='PAYPAL', amount: Money = None):
    """
    Gets the single payment record associated with the order (created in create_order)
    and updates it with the selected provider and amount.
    """
    try:
        # Fetch the one-and-only payment record for this order.
        # This record is created by the create_order view.
        payment = Payment.objects.get(order=order)

        payment_amount = amount or order.total

        # Update the payment with the provider and amount for this attempt
        payment.provider = provider
        payment.amount = payment_amount

        # If the payment failed previously, reset it to PENDING to allow a new attempt
        if payment.status == 'FAILED':
            payment.status = 'PENDING'

        # Save the updated fields
        payment.save(update_fields=['provider', 'amount', 'status'])

        # Return 'created=False' because we fetched and updated, not created.
        return payment, False

    except Payment.DoesNotExist:
        # Fallback: If create_order *failed* to make a payment, create one now.
        logger.warning(f"Payment record not found for order {order.id}. Creating a new one.")
        payment = Payment.objects.create(
            order=order,
            provider=provider,
            amount=amount or order.total,
            status='PENDING'
        )
        return payment, True

    except Exception as e:
        # Catch other potential errors (like MultipleObjectsReturned)
        logger.exception(f"Error in get_or_create_payment_safe: {e}")
        # Re-raise the exception to be handled by the view
        raise e

# ---------------------------------------------------------
# CREATE PAYPAL PAYMENT
# ---------------------------------------------------------
@csrf_exempt
@require_POST
def create_paypal_payment(request):
    """Create a PayPal order while supporting Money and currency conversion."""
    try:
        data = json.loads(request.body)
        order_id = data.get('order_id')
        if not order_id:
            return JsonResponse({'success': False, 'error': 'Order ID is required'}, status=400)

        order = get_object_or_404(Order, id=order_id)
        if order.status != 'PENDING':
            return JsonResponse({'success': False, 'error': f'Order already {order.status.lower()}'}, status=400)

        target_currency = data.get('currency', 'USD')
        base_money = order.total  # Money object

        if not is_paypal_currency_supported(target_currency):
            return JsonResponse({
                'success': False,
                'error': f'Currency {target_currency} not supported by PayPal'
            }, status=400)

        # --- Currency Conversion (if needed) ---
        if base_money.currency != target_currency:
            from core.utils import get_exchange_rate
            rate = get_exchange_rate(base_money.currency, target_currency)
            converted_amount = (base_money.amount * rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            payment_amount = Money(converted_amount, target_currency)
        else:
            payment_amount = base_money

        # Safe payment record
        payment, created = get_or_create_payment_safe(order, 'PAYPAL', payment_amount)
        if not created and payment.status != 'PENDING':
            return JsonResponse({'success': False, 'error': f'Payment already {payment.status.lower()}'}, status=400)

        # Create PayPal order
        result = create_paypal_order(
            float(payment_amount.amount),
            payment_amount.currency.code,
            order_id,
            request
        )

        if 'id' in result:
            payment.status = 'PROCESSING'
            payment.transaction_id = result['id']
            payment.raw_response = result
            payment.save()

            approval_url = next(
                (link['href'] for link in result.get('links', []) if link.get('rel') == 'approve'),
                None
            )

            return JsonResponse({
                'success': True,
                'order_id': result['id'],
                'approval_url': approval_url,
                'status': result.get('status'),
                'message': 'PayPal order created successfully'
            })
        else:
            error_msg = result.get('error', 'PayPal order creation failed')
            return JsonResponse({'success': False, 'error': error_msg, 'details': result.get('details')}, status=400)

    except Exception as e:
        logger.exception(f'PayPal payment creation failed: {e}')
        return JsonResponse({'success': False, 'error': 'Payment creation failed', 'details': str(e)}, status=500)


# ---------------------------------------------------------
# INITIATE MPESA PAYMENT
# ---------------------------------------------------------
@csrf_exempt
@require_POST
def initiate_payment(request):
    """
    ✅ FIXED: Initiate M-Pesa payment with proper payment record handling
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON data'}, status=400)

    order_id = data.get('order_id')
    provider = data.get('provider')
    phone = data.get('phone')
    amount_str = data.get('amount')
    currency_str = data.get('currency')

    if not all([order_id, provider, amount_str, currency_str]):
        return JsonResponse({'success': False, 'error': 'Missing required parameters'}, status=400)

    order = get_object_or_404(Order, id=order_id)
    if provider != 'MPESA':
        return JsonResponse({'success': False, 'error': 'Use PayPal endpoint for PayPal'}, status=400)

    # Create Money object
    try:
        amount_money = Money(Decimal(str(amount_str)), currency_str)
    except Exception:
        return JsonResponse({'success': False, 'error': 'Invalid amount format'}, status=400)

    # ✅ FIX: Get existing payment or create new one
    try:
        with transaction.atomic():
            payment = Payment.objects.select_for_update().get(order=order)

            # ✅ CRITICAL: Reset payment if it's in a terminal state (allow retry)
            if payment.status == 'FAILED':
                logger.info(f"Resetting payment {payment.id} from {payment.status} to allow new attempt")
                payment.status = 'PENDING'
                payment.checkout_request_id = None
                payment.transaction_id = None
                payment.raw_response = None
                payment.result_code = None
                payment.result_description = None

            payment.provider = 'MPESA'
            payment.amount = amount_money
            payment.phone_number = phone

    except Payment.DoesNotExist:
        logger.warning(f"No payment found for order {order_id}, creating new one")
        payment = Payment.objects.create(
            order=order,
            provider='MPESA',
            amount=amount_money,
            phone_number=phone,
            status='PENDING'
        )

    # --- Convert to KES ---
    mpesa_amount = amount_money
    if amount_money.currency.code != 'KES':
        from core.utils import get_exchange_rate
        rate = get_exchange_rate(amount_money.currency, 'KES')
        kes_amount = (amount_money.amount * rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        mpesa_amount = Money(kes_amount, 'KES')

        payment.original_amount = amount_money
        payment.converted_amount = mpesa_amount
        payment.exchange_rate = rate
        payment.save(update_fields=['original_amount', 'converted_amount', 'exchange_rate'])

    # Call M-Pesa API
    result = initiate_mpesa_payment(mpesa_amount.amount, phone, order_id)
    logger.info('[initiate_payment] M-Pesa result: %s', result)

    if isinstance(result, dict) and result.get('ResponseCode') == '0':
        payment.status = 'PROCESSING'
        payment.provider = 'MPESA'
        payment.phone_number = phone
        payment.raw_response = result
        payment.checkout_request_id = result.get('CheckoutRequestID')
        payment.save(update_fields=['status', 'provider', 'phone_number', 'raw_response', 'checkout_request_id'])

        return JsonResponse({
            'success': True,
            'checkout_request_id': result.get('CheckoutRequestID'),
            'message': 'M-Pesa payment initiated successfully'
        })
    else:
        error_msg = result.get('errorMessage', 'M-Pesa initiation failed')
        payment.status = 'FAILED'
        payment.failure_type = 'INITIATION_FAILED'
        payment.result_description = error_msg
        payment.save()
        return JsonResponse({'success': False, 'error': error_msg})

@csrf_exempt
def mpesa_status(request):
    """
    Unified M-Pesa payment status endpoint.
    - Supports simple polling (client-side)
    - Handles webhook fallback & timeout safety
    - Returns clean, consistent JSON responses
    """
    checkout_request_id = request.GET.get('checkout_request_id')

    if not checkout_request_id:
        return JsonResponse({'status': 'error', 'message': 'checkout_request_id is required'}, status=400)

    try:
        payment = Payment.objects.get(checkout_request_id=checkout_request_id, provider='MPESA')
        processing_time = timezone.now() - payment.created_at
        timeout_threshold = timedelta(minutes=20)

        # Handle timeout or webhook reprocessing
        if payment.status.upper() == 'PROCESSING':
            with transaction.atomic():
                payment = Payment.objects.select_for_update().get(id=payment.id)

                # Timeout handling
                if processing_time > timeout_threshold:
                    if not payment.raw_response:
                        payment.status = 'FAILED'
                        payment.failure_type = 'TIMEOUT'
                        payment.result_description = 'Payment timeout after 20 minutes - no callback received'
                        payment.save(update_fields=['status', 'failure_type', 'result_description'])
                        logger.info(f"Payment {payment.id} timed out (no webhook)")
                    elif payment.raw_response:
                        try:

                            if isinstance(payment.raw_response, (str, bytes, bytearray)):
                                data = json.loads(payment.raw_response)
                            else:
                                data = payment.raw_response

                            process_mpesa_webhook_data(payment, data)
                            logger.info(f"Webhook data reprocessed for payment {payment.id}")
                        except Exception as e:
                            logger.warning(f"Failed to reprocess webhook for {payment.id}: {e}")

        # Construct user-friendly response
        response_data = {
            'checkout_request_id': checkout_request_id,
            'status': payment.status.lower(),
            'transaction_id': payment.transaction_id,
            'failure_type': payment.failure_type,
            'result_code': payment.result_code,
            'result_description': payment.result_description,
            'amount': str(payment.amount),
            'order_id': payment.order.id,
            'retry_count': payment.retry_count,
            'webhook_received': bool(payment.raw_response),
            'can_retry': payment.failure_type in ['TEMPORARY', 'USER_CANCELLED', 'TIMEOUT']
                         and (payment.failure_type != 'TEMPORARY' or payment.retry_count < 3),
        }

        # Add friendly message
        if payment.status.upper() == 'COMPLETED':
            response_data['message'] = 'Payment completed successfully'
        elif payment.status.upper() == 'FAILED':
            response_data['message'] = payment.result_description or 'Payment failed'
        else:
            response_data['message'] = 'Payment is still processing'

        return JsonResponse(response_data)

    except Payment.DoesNotExist:
        logger.warning(f"No payment found for checkout_request_id: {checkout_request_id}")
        return JsonResponse({
            'checkout_request_id': checkout_request_id,
            'status': 'unknown',
            'message': 'Payment not found'
        }, status=404)

    except Exception as e:
        logger.error(f"Error checking M-Pesa status: {e}")
        return JsonResponse({'status': 'error', 'message': 'Internal server error'}, status=500)

@csrf_exempt
@require_POST
def retry_mpesa_payment(request, payment_id):
    """Retry a failed M-Pesa payment (optional for cancelled payments)"""
    try:
        payment = get_object_or_404(Payment, id=payment_id, provider='MPESA')

        # Check if payment can be retried
        if payment.failure_type not in ['TEMPORARY', 'USER_CANCELLED']:
            return JsonResponse({
                'success': False,
                'error': 'This payment cannot be retried'
            }, status=400)

        # Check retry limits (only for temporary failures)
        if payment.failure_type == 'TEMPORARY' and payment.retry_count >= 3:
            return JsonResponse({
                'success': False,
                'error': 'Maximum retry attempts exceeded'
            }, status=400)

        # Use converted amount if available, otherwise original amount
        amount_to_use = payment.converted_amount if payment.converted_amount else payment.amount

        # Initiate new payment
        result = initiate_mpesa_payment(
            amount_to_use.amount,
            payment.phone_number,
            payment.order.id
        )

        if result.get('ResponseCode') == '0':
            # Update payment record
            payment.status = 'PROCESSING'
            payment.retry_count += 1
            payment.last_retry_at = timezone.now()
            payment.checkout_request_id = result.get('CheckoutRequestID')
            payment.save()

            return JsonResponse({
                'success': True,
                'checkout_request_id': result.get('CheckoutRequestID'),
                'message': 'M-Pesa payment retried successfully'
            })
        else:
            return JsonResponse({
                'success': False,
                'error': result.get('errorMessage', 'M-Pesa payment failed')
            })

    except Exception as e:
        logger.error(f'Payment retry failed: {str(e)}')
        return JsonResponse({
            'success': False,
            'error': f'Payment retry failed: {str(e)}'
        })



# ---------------------------------------------------------
# WEBHOOK HANDLERS
# ---------------------------------------------------------
@csrf_exempt
def payment_webhook(request, provider):
    if provider == 'MPESA':
        return handle_mpesa_webhook(request)
    elif provider == 'PAYPAL':
        return handle_paypal_webhook(request)
    return JsonResponse({'error': 'Invalid provider'}, status=400)


@csrf_exempt
@require_POST
@transaction.atomic
def process_payment(request, order_id):
    """
    FIXED: Finalize payment after frontend confirmation.
    Now handles race conditions where webhook has already processed the payment.
    """
    logger.info(f'[process_payment] Finalizing payment for order {order_id}')

    try:
        order = get_object_or_404(Order, id=order_id)

        # Lock the order to prevent concurrent modifications
        with transaction.atomic():
            order = Order.objects.select_for_update(nowait=False).get(pk=order.pk)

        # ✅ FIX: Check if already paid (webhook may have processed it)
        if order.status == 'PAID':
            logger.info(f'[process_payment] Order {order_id} already paid (webhook processed it)')
            return JsonResponse({
                'success': True,
                'status': 'success',
                'message': 'Payment already completed',
                'redirect_url': reverse('orders:success', args=[order.id])
            })

        # Prevent re-processing other states
        if order.status not in ['PENDING', 'PROCESSING']:
            logger.warning(f'[process_payment] Order {order_id} is already {order.status}.')
            return JsonResponse({
                'success': False,
                'status': 'error',
                'message': f'Order is already {order.status.lower()}',
                'redirect_url': reverse('orders:success', args=[order.id])
            })

        payment_method = request.POST.get('payment_method')
        logger.info(f'[process_payment] Method: {payment_method}')

        payment = get_object_or_404(Payment.objects.select_for_update(), order=order)

        # ------------------------------------------------------------------
        #                            M-PESA
        # ------------------------------------------------------------------
        if payment_method == 'mpesa':
            checkout_request_id = request.POST.get('checkout_request_id')

            if not checkout_request_id:
                logger.error('[process_payment] M-Pesa: Missing checkout_request_id')
                return JsonResponse({
                    'status': 'error',
                    'message': 'Missing M-Pesa transaction reference'
                }, status=400)

            # Verify the payment record matches
            if payment.checkout_request_id != checkout_request_id or payment.provider != 'MPESA':
                logger.error(
                    f'[process_payment] M-Pesa: Mismatch. Expected {payment.checkout_request_id} '
                    f'but got {checkout_request_id}'
                )
                return JsonResponse({
                    'status': 'error',
                    'message': 'M-Pesa transaction mismatch'
                }, status=400)

            # ✅ FIX: If webhook already marked it as completed, skip mark_as_paid
            if payment.status == 'COMPLETED':
                logger.info(f'[process_payment] Payment {payment.id} already COMPLETED by webhook')
                # Just ensure the order status is synced
                if order.status == 'PENDING':
                    try:
                        order.mark_as_paid(payment_method='MPESA')
                    except (PermissionError, ValidationError) as e:
                        logger.warning(f'Order {order.id} already processed: {e}')
                        # Order is already paid, continue
            else:
                # Payment not yet completed, set it now
                payment.status = 'COMPLETED'
                payment.phone_number = request.POST.get('phone_number', payment.phone_number)
                payment.save()

                # Mark order as paid
                try:
                    order.mark_as_paid(payment_method='MPESA')
                except (PermissionError, ValidationError) as e:
                    logger.warning(f'Order {order.id} already marked as paid: {e}')

        # ------------------------------------------------------------------
        #                            PAYPAL
        # ------------------------------------------------------------------
        elif payment_method == 'paypal':
            paypal_order_id = request.POST.get('paypal_order_id')

            if not paypal_order_id:
                logger.error('[process_payment] PayPal: Missing paypal_order_id')
                return JsonResponse({
                    'status': 'error',
                    'message': 'Missing PayPal order ID'
                }, status=400)

            # ✅ FIX: Check if already completed by webhook
            if payment.status == 'COMPLETED':
                logger.info(f'[process_payment] Payment {payment.id} already COMPLETED by webhook')
                if order.status == 'PENDING':
                    try:
                        order.mark_as_paid(payment_method='PAYPAL')
                    except (PermissionError, ValidationError) as e:
                        logger.warning(f'Order {order.id} already processed: {e}')
            else:
                payment.status = 'COMPLETED'
                payment.provider = 'PAYPAL'
                payment.transaction_id = paypal_order_id
                payment.raw_response = {
                    'status': 'COMPLETED',
                    'id': paypal_order_id,
                    'details': request.POST.dict()
                }
                payment.save()

                # Mark order as paid
                try:
                    order.mark_as_paid(payment_method='PAYPAL')
                except (PermissionError, ValidationError) as e:
                    logger.warning(f'Order {order.id} already marked as paid: {e}')

        # ------------------------------------------------------------------
        #                        INVALID METHOD
        # ------------------------------------------------------------------
        else:
            logger.error(f'[process_payment] Invalid payment method: {payment_method}')
            return JsonResponse({
                'status': 'error',
                'message': 'Invalid payment method'
            }, status=400)

        # --- COMMON SUCCESS LOGIC ---
        clear_cart_after_payment(order)
        logger.info(f'[process_payment] Order {order.id} finalized successfully')

        return JsonResponse({
            'success': True,
            'status': 'success',
            'message': 'Payment completed successfully',
            'transaction_id': payment.transaction_id,
            'redirect_url': reverse('orders:success', args=[order.id])
        })

    except Payment.DoesNotExist:
        logger.error(f'[process_payment] No payment record found for order {order_id}')
        return JsonResponse({
            'status': 'error',
            'message': 'Payment record not found.'
        }, status=404)
    except Order.DoesNotExist:
        logger.error(f'[process_payment] Order {order_id} not found')
        return JsonResponse({
            'status': 'error',
            'message': 'Order not found.'
        }, status=404)
    except Exception as e:
        logger.exception(f'[process_payment] Unknown error for order {order_id}: {e}')
        return JsonResponse({
            'status': 'error',
            'message': 'An internal error occurred.'
        }, status=500)

@csrf_exempt
def test_mpesa_connection(request):
    """Test endpoint to check M-Pesa API connectivity"""
    try:
        # Test authentication only
        auth_url = "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
        response = requests.get(
            auth_url,
            auth=(settings.MPESA_CONSUMER_KEY, settings.MPESA_CONSUMER_SECRET),
            timeout=10
        )

        if response.status_code == 200:
            return JsonResponse({
                'success': True,
                'message': 'M-Pesa API connection successful'
            })
        else:
            return JsonResponse({
                'success': False,
                'message': f'M-Pesa API connection failed: {response.status_code}'
            })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'M-Pesa API connection error: {str(e)}'
        })


@csrf_exempt
def debug_payment(request, checkout_request_id):
    """Debug endpoint to check payment status and webhook data"""
    try:
        payment = Payment.objects.get(checkout_request_id=checkout_request_id)

        debug_info = {
            'payment_id': payment.id,
            'order_id': payment.order.id,
            'status': payment.status,
            'provider': payment.provider,
            'checkout_request_id': payment.checkout_request_id,
            'created_at': payment.created_at,
            'result_code': payment.result_code,
            'result_description': payment.result_description,
            'failure_type': payment.failure_type,
            'phone_number': payment.phone_number,
            'amount': str(payment.amount),
            'currency': payment.currency,
            'has_raw_response': bool(payment.raw_response),
            'has_raw_callback': bool(payment.raw_callback),
            'raw_response_keys': list(payment.raw_response.keys()) if payment.raw_response else [],
            'raw_callback_keys': list(payment.raw_callback.keys()) if payment.raw_callback else [],
        }

        return JsonResponse({'success': True, 'debug_info': debug_info})

    except Payment.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Payment not found'})




@csrf_exempt

def paypal_payment_return(request, order_id):
    """Handle PayPal return URL - payment success"""
    order = get_object_or_404(Order, id=order_id)

    # Check if payment was completed via webhook
    payment = Payment.objects.filter(order=order, provider='PAYPAL').first()

    if payment and payment.status == 'COMPLETED':
        # Use the correct URL name with order_id parameter
        return redirect('orders:success', order_id=order_id)
    else:
        # Payment might still be processing
        return render(request, 'payment/paypal_processing.html', {
            'order': order,
            'payment': payment
        })


@csrf_exempt
def paypal_payment_cancel(request, order_id):
    """Handle PayPal cancel URL - payment cancelled"""
    order = get_object_or_404(Order, id=order_id)

    # Update payment status if exists
    payment = Payment.objects.filter(order=order, provider='PAYPAL').first()
    if payment and payment.status == 'PENDING':
        payment.status = 'FAILED'
        payment.failure_type = 'USER_CANCELLED'
        payment.save()

    return render(request, 'payment/paypal_cancelled.html', {
        'order': order,
        'payment': payment
    })


@csrf_exempt
def paypal_status(request):
    """Check PayPal payment status"""
    order_id = request.GET.get('order_id')


    if not order_id:
        return JsonResponse({'error': 'Order ID required'}, status=400)

    try:
        payment = Payment.objects.get(order_id=order_id, provider='PAYPAL')
        return JsonResponse({
            'status': payment.status.lower(),
            'transaction_id': payment.transaction_id,
            'order_id': payment.order.id
        })
    except Payment.DoesNotExist:
        return JsonResponse({'status': 'not_found'}, status=404)
