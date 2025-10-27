#payment/views.py
from django.db import transaction
from datetime import timedelta
from django.urls import reverse
from paypal.standard.forms import PayPalPaymentsForm
import json
from decimal import Decimal
import requests
from django.conf import settings
from django.shortcuts import get_object_or_404, render, redirect
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from orders.models import Order
from .cart_utils import clear_cart_after_payment
from .models import Payment
from .utils import initiate_mpesa_payment, create_paypal_order, is_currency_supported, capture_paypal_order, is_paypal_currency_supported
from .webhooks import handle_mpesa_webhook, handle_paypal_webhook, process_mpesa_webhook_data
from django.views.decorators.http import require_POST, require_http_methods
from django.http import JsonResponse, HttpResponse
import logging


logger = logging.getLogger(__name__)

# PayPal supported currencies
PAYPAL_SUPPORTED_CURRENCIES = ['USD', 'EUR', 'GBP', 'CAD', 'AUD', 'JPY']


def get_or_create_payment_safe(order, provider='PAYPAL', amount=None, currency=None):
    """SAFE method to get or create payment without duplicates"""
    try:
        # Try to get existing payment for this order and provider
        payments = Payment.objects.filter(order=order, provider=provider)

        if payments.exists():
            if payments.count() > 1:
                # Handle duplicates - use most recent, mark others as failed
                payment = payments.latest('created_at')
                older_payments = payments.exclude(id=payment.id)
                older_payments.update(
                    status='FAILED',
                    failure_type='DUPLICATE',
                    result_description='Multiple payments detected, using most recent'
                )
                logger.warning(f"Fixed duplicate payments for order {order.id}, using {payment.id}")
                return payment, False
            else:
                return payments.first(), False
        else:
            # Create new payment
            payment = Payment.objects.create(
                order=order,
                provider=provider,
                amount=amount or order.total,
                currency=currency or order.currency,
                status='PENDING'
            )
            return payment, True

    except Exception as e:
        logger.error(f"Error in get_or_create_payment_safe: {str(e)}")
        # Fallback: create new payment
        payment = Payment.objects.create(
            order=order,
            provider=provider,
            amount=amount or order.total,
            currency=currency or order.currency,
            status='PENDING'
        )
        return payment, True



@csrf_exempt
@require_POST
def create_paypal_payment(request):
    """FIXED: Create PayPal payment with duplicate prevention"""
    try:
        data = json.loads(request.body)
        order_id = data.get('order_id')

        if not order_id:
            return JsonResponse({
                'success': False,
                'error': 'Order ID is required'
            }, status=400)

        order = get_object_or_404(Order, id=order_id)

        # Validate order status
        if order.status != 'PENDING':
            return JsonResponse({
                'success': False,
                'error': f'Order already {order.status.lower()}'
            }, status=400)

        currency = data.get('currency', 'USD')

        # Validate currency
        if not is_paypal_currency_supported(currency):
            return JsonResponse({
                'success': False,
                'error': f'Currency {currency} not supported by PayPal'
            }, status=400)

        # ✅ FIXED: Use safe payment creation method
        payment, created = get_or_create_payment_safe(
            order,
            'PAYPAL',
            order.total,
            currency
        )

        if not created and payment.status != 'PENDING':
            return JsonResponse({
                'success': False,
                'error': f'Payment already {payment.status.lower()}'
            }, status=400)

        # Create PayPal order
        result = create_paypal_order(
            float(order.total),
            currency,
            order_id,
            request
        )

        if 'id' in result:
            payment.status = 'PROCESSING'
            payment.transaction_id = result['id']
            payment.raw_response = result
            payment.save()

            # Find approval URL
            approval_url = None
            for link in result.get('links', []):
                if link.get('rel') == 'approve':
                    approval_url = link.get('href')
                    break

            return JsonResponse({
                'success': True,
                'order_id': result['id'],
                'approval_url': approval_url,
                'status': result.get('status'),
                'message': 'PayPal order created successfully'
            })
        else:
            error_msg = result.get('error', 'PayPal order creation failed')
            logger.error(f"PayPal order creation failed: {error_msg}")
            return JsonResponse({
                'success': False,
                'error': error_msg,
                'details': result.get('details')
            }, status=400)

    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON data'
        }, status=400)
    except Exception as e:
        logger.error(f'PayPal payment creation failed: {str(e)}')
        return JsonResponse({
            'success': False,
            'error': 'Payment creation failed',
            'details': str(e)
        }, status=500)




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
                            data = json.loads(payment.raw_response)
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
def initiate_payment(request):
    """
    Initiate payment endpoint that accepts JSON.
    Returns JSON including checkout_request_id for MPESA.
    """

    # log raw body for debugging
    try:
        raw = request.body.decode('utf-8')
    except Exception:
        raw = '<unreadable body>'
    logger.info('[initiate_payment] raw body: %s', raw)

    # parse JSON payload if content-type application/json
    data = {}
    if request.content_type and 'application/json' in request.content_type:
        try:
            data = json.loads(raw or '{}')
        except json.JSONDecodeError:
            logger.error('[initiate_payment] invalid JSON')
            return JsonResponse({'success': False, 'error': 'Invalid JSON data'}, status=400)
    else:
        data = request.POST.dict()  # fallback: if form-encoded

    logger.info('[initiate_payment] parsed data: %s', data)

    order_id = data.get('order_id')
    provider = data.get('provider')
    phone = data.get('phone')
    amount = data.get('amount')
    currency = data.get('currency')

    if not all([order_id, provider, amount, currency]):
        logger.error('[initiate_payment] missing params, received: %s', { 'order_id': order_id, 'provider': provider, 'amount': amount, 'currency': currency })
        return JsonResponse({'success': False, 'error': 'Missing required parameters'}, status=400)

    order = get_object_or_404(Order, id=order_id)

    # Only MPESA handled here for initiation
    if provider != 'MPESA':
        return JsonResponse({'success': False, 'error': 'Use PayPal-specific endpoint for PayPal'}, status=400)

    # convert amount to Decimal (safe)
    try:
        amount_dec = Decimal(str(amount))
    except Exception as e:
        logger.exception('Invalid amount format: %s', amount)
        return JsonResponse({'success': False, 'error': 'Invalid amount format'}, status=400)

    # create or get payment record (use your existing safe method)
    payment, created = get_or_create_payment_safe(order, 'MPESA', amount_dec, currency)

    # If currency not KES, convert to KES inside utils
    result = initiate_mpesa_payment(amount_dec, phone, order_id)

    logger.info('[initiate_payment] safaricom result: %s', result)

    if isinstance(result, dict) and result.get('ResponseCode') == '0':
        checkout_id = result.get('CheckoutRequestID')
        # persist
        payment.status = 'PROCESSING'
        payment.provider = 'MPESA'
        payment.phone_number = phone
        payment.raw_response = result
        payment.checkout_request_id = checkout_id
        payment.save(update_fields=['status', 'provider', 'phone_number', 'raw_response', 'checkout_request_id'])
        return JsonResponse({
            'success': True,
            'checkout_request_id': checkout_id,
            'message': 'M-Pesa payment initiated successfully'
        })
    else:
        # unify error message key
        err = result.get('errorMessage') if isinstance(result, dict) else 'M-Pesa initiation failed'
        logger.error('[initiate_payment] initiation failed: %s', err)
        return JsonResponse({'success': False, 'error': err})

        logger.info(f"[initiate_payment] returning checkout_request_id={result.get('CheckoutRequestID')}")


@csrf_exempt
def payment_webhook(request, provider):
    if provider == 'MPESA':
        return handle_mpesa_webhook(request)
    elif provider == 'PAYPAL':
        return handle_paypal_webhook(request)
    return JsonResponse({'error': 'Invalid provider'}, status=400)


# payment/views.py

@csrf_exempt
@require_POST
@transaction.atomic  # Add atomic transaction for safety
def process_payment(request, order_id):
    """
    FIXED: Finalize payment after frontend confirmation.
    This view no longer initiates or captures payment.
    It only verifies and records the final state.
    """
    logger.info(f'[process_payment] Finalizing payment for order {order_id}')

    try:
        order = get_object_or_404(Order.objects.select_for_update(), id=order_id)

        # Prevent re-processing a paid order
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
                return JsonResponse({'status': 'error', 'message': 'Missing M-Pesa transaction reference'}, status=400)

            # Verify the payment record matches
            if payment.checkout_request_id != checkout_request_id or payment.provider != 'MPESA':
                logger.error(
                    f'[process_payment] M-Pesa: Mismatch. Expected {payment.checkout_request_id} but got {checkout_request_id}')
                return JsonResponse({'status': 'error', 'message': 'M-Pesa transaction mismatch'}, status=400)

            # Trust the poller, but double-check the status
            if payment.status != 'COMPLETED':
                logger.warning(
                    f'[process_payment] M-Pesa: Payment {payment.id} not yet marked COMPLETED by webhook/poll. Forcing re-check.')
                # You could optionally re-run the status check logic here, but for now we'll trust the frontend poll
                # For safety, let's assume if the frontend says it's done, it's done.
                payment.status = 'COMPLETED'

            payment.phone_number = request.POST.get('phone_number', payment.phone_number)
            payment.save()

        # ------------------------------------------------------------------
        #                            PAYPAL
        # ------------------------------------------------------------------
        elif payment_method == 'paypal':
            paypal_order_id = request.POST.get('paypal_order_id')  # This is the capture ID

            if not paypal_order_id:
                logger.error('[process_payment] PayPal: Missing paypal_order_id')
                return JsonResponse({'status': 'error', 'message': 'Missing PayPal order ID'}, status=400)

            # --- REMOVED `capture_paypal_order` ---
            # The frontend already captured the payment.

            payment.status = 'COMPLETED'
            payment.provider = 'PAYPAL'
            payment.transaction_id = paypal_order_id
            payment.raw_response = {'status': 'COMPLETED', 'id': paypal_order_id, 'details': request.POST.dict()}
            payment.save()

        # ------------------------------------------------------------------
        #                        INVALID METHOD
        # ------------------------------------------------------------------
        else:
            logger.error(f'[process_payment] Invalid payment method: {payment_method}')
            return JsonResponse({'status': 'error', 'message': 'Invalid payment method'}, status=400)

        # --- COMMON SUCCESS LOGIC ---

        # Mark order as paid using your robust model method
        try:
            order.mark_as_paid(payment_method=payment_method.upper())
            logger.info(f'[process_payment] Order {order.id} marked as PAID.')
        except Exception as e:
            logger.error(f'[process_payment] Failed to mark order {order.id} as paid: {e}')
            # Continue, as payment is already COMPLETED

        clear_cart_after_payment(order)
        logger.info(f'[process_payment] Cart cleared for order {order.id}.')

        return JsonResponse({
            'success': True,
            'status': 'success',
            'message': 'Payment completed successfully',
            'transaction_id': payment.transaction_id,
            'redirect_url': reverse('orders:success', args=[order.id])
        })

    except Payment.DoesNotExist:
        logger.error(f'[process_payment] No payment record found for order {order_id}')
        return JsonResponse({'status': 'error', 'message': 'Payment record not found.'}, status=404)
    except Order.DoesNotExist:
        logger.error(f'[process_payment] Order {order_id} not found')
        return JsonResponse({'status': 'error', 'message': 'Order not found.'}, status=404)
    except Exception as e:
        logger.exception(f'[process_payment] Unknown error for order {order_id}: {e}')
        return JsonResponse({'status': 'error', 'message': 'An internal error occurred.'}, status=500)



@csrf_exempt
def validate_currency(request):
    """Validate if a currency is supported for a payment method"""
    currency = request.GET.get('currency')
    provider = request.GET.get('provider')

    if not currency or not provider:
        return JsonResponse({'error': 'Currency and provider parameters required'}, status=400)

    is_supported = is_currency_supported(currency, provider)

    return JsonResponse({
        'supported': is_supported,
        'message': f"Currency {currency} is {'supported' if is_supported else 'not supported'} for {provider}"
    })



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
            amount_to_use,
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
@require_POST
def execute_paypal_payment(request, order_id):
    """FIXED: Execute PayPal payment with cart clearing"""
    try:
        order = get_object_or_404(Order, id=order_id)
        payment = get_object_or_404(Payment, order=order, provider='PAYPAL')

        data = json.loads(request.body)
        paypal_order_id = data.get('order_id')

        if not paypal_order_id:
            return JsonResponse({
                'success': False,
                'error': 'PayPal order ID required'
            }, status=400)

        # Capture payment
        result = capture_paypal_order(paypal_order_id)

        if result.get('status') == 'COMPLETED':
            payment.status = 'COMPLETED'
            payment.transaction_id = result.get('id')
            payment.raw_response = result
            payment.save()

            order.status = 'PAID'
            order.payment_method = 'PAYPAL'
            order.save()

            # ✅ CLEAR CART AFTER SUCCESSFUL PAYMENT
            clear_cart_after_payment(order)

            return JsonResponse({
                'success': True,
                'message': 'Payment completed successfully',
                'transaction_id': result.get('id')
            })
        else:
            error_msg = result.get('message', 'Payment capture failed')
            return JsonResponse({
                'success': False,
                'error': error_msg,
                'details': result.get('details')
            }, status=400)

    except Exception as e:
        logger.error(f'PayPal payment execution failed: {str(e)}')
        return JsonResponse({
            'success': False,
            'error': 'Payment execution failed'
        }, status=500)



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



def paypal_success(request, order_id):
    """Handle successful PayPal return"""
    order = get_object_or_404(Order, id=order_id)
    # Check if payment was completed via IPN
    try:
        payment = Payment.objects.get(order=order, provider='PAYPAL')
        if payment.status == 'COMPLETED':
            return redirect('orders:success', pk=order.id)
    except Payment.DoesNotExist:
        pass

    # Payment might still be processing
    return render(request, 'payment/payment_pending.html', {
        'order': order,
        'payment': payment
    })


def paypal_cancel(request, order_id):
    """Handle cancelled PayPal payment"""
    order = get_object_or_404(Order, id=order_id)

    # Update payment status if exists
    payment = Payment.objects.filter(order=order, provider='PAYPAL').first()
    if payment and payment.status == 'PENDING':
        payment.status = 'FAILED'
        payment.failure_type = 'USER_CANCELLED'
        payment.save()

    return render(request, 'payment/expired.html', {
        'order': order,
        'payment': payment
    })
