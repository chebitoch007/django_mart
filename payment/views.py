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
                    if not payment.raw_callback:
                        payment.status = 'FAILED'
                        payment.failure_type = 'TIMEOUT'
                        payment.result_description = 'Payment timeout after 20 minutes - no callback received'
                        payment.save(update_fields=['status', 'failure_type', 'result_description'])
                        logger.info(f"Payment {payment.id} timed out (no webhook)")
                    elif payment.raw_callback:
                        try:
                            data = json.loads(payment.raw_callback)
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
            'webhook_received': bool(payment.raw_callback),
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


@csrf_exempt
@require_POST
def process_payment(request, order_id):
    """
    Process/finalize payment. Accepts either application/json or form data.
    Handles both M-Pesa and PayPal. Includes robust logging and fallback handling.
    """
    logger.info('[process_payment] Initiating payment processing for order %s', order_id)

    # --- Raw body logging ---
    try:
        raw = request.body.decode('utf-8')
    except Exception:
        raw = '<unreadable>'
    logger.debug('[process_payment] raw POST data: %s', raw)

    # --- Parse incoming data ---
    data = {}
    if request.content_type and 'application/json' in request.content_type:
        try:
            data = json.loads(raw or '{}')
        except json.JSONDecodeError:
            logger.error('[process_payment] invalid JSON body')
            return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)
    else:
        data = request.POST.dict()

    logger.debug('[process_payment] parsed fields: %s', data)

    # --- Fetch order ---
    order = get_object_or_404(Order, id=order_id)
    payment_method = data.get('payment_method') or data.get('method')
    logger.info('[process_payment] Payment method: %s', payment_method)

    # ------------------------------------------------------------------
    #                            M-PESA
    # ------------------------------------------------------------------
    if payment_method == 'mpesa':
        checkout_request_id = (
            data.get('checkout_request_id')
            or data.get('checkoutRequestId')
            or data.get('checkoutId')
        )
        phone_number = (
            data.get('phone_number')
            or data.get('phone')
            or data.get('msisdn')
        )
        amount = data.get('amount')
        currency = data.get('currency', 'KES')

        logger.debug('[process_payment] M-Pesa data => checkout_request_id=%s, phone=%s, amount=%s, currency=%s',
                     checkout_request_id, phone_number, amount, currency)

        # --- Fallback: initiate or reuse existing payment ---
        if not checkout_request_id:
            logger.info('[process_payment] No checkout_request_id provided, checking existing payments')
            existing = Payment.objects.filter(order=order, provider='MPESA', status__in=['PENDING', 'PROCESSING'])
            if existing.exists():
                payment = existing.latest('created_at')
                checkout_request_id = payment.checkout_request_id
                logger.info('[process_payment] Found existing checkout_request_id=%s', checkout_request_id)
            else:
                if not phone_number or not amount:
                    return JsonResponse({
                        'status': 'error',
                        'message': 'Phone number and amount required to initiate payment',
                        'debug': 'No checkout_request_id and missing phone/amount'
                    }, status=400)
                try:
                    amount_dec = Decimal(str(amount))
                    result = initiate_mpesa_payment(amount_dec, phone_number, order_id)
                    if result.get('ResponseCode') == '0':
                        checkout_request_id = result.get('CheckoutRequestID')
                        payment = Payment.objects.create(
                            order=order,
                            provider='MPESA',
                            status='PROCESSING',
                            amount=amount_dec,
                            currency=currency,
                            phone_number=phone_number,
                            checkout_request_id=checkout_request_id,
                            raw_response=result
                        )
                        logger.info('[process_payment] Created new payment with checkout_request_id=%s', checkout_request_id)
                    else:
                        error_msg = result.get('errorMessage', 'M-Pesa initiation failed')
                        return JsonResponse({'status': 'error', 'message': error_msg}, status=400)
                except Exception as e:
                    logger.error('[process_payment] Failed to initiate M-Pesa: %s', str(e))
                    return JsonResponse({'status': 'error', 'message': 'Failed to initiate payment'}, status=400)

        # --- Retrieve or create placeholder payment ---
        try:
            payment = Payment.objects.get(checkout_request_id=checkout_request_id, provider='MPESA')
            logger.info('[process_payment] Found payment record id=%s status=%s', payment.id, payment.status)
            if payment.status == 'COMPLETED':
                order.status = 'PAID'
                order.payment_method = 'MPESA'
                order.save()
                clear_cart_after_payment(order)
                return JsonResponse({
                    'success': True,
                    'status': 'success',
                    'message': 'M-Pesa payment already completed',
                    'redirect_url': f'/orders/success/{order.id}/'
                })
            else:
                return JsonResponse({
                    'status': payment.status.lower(),
                    'failure_type': payment.failure_type,
                    'result_description': payment.result_description,
                    'checkout_request_id': checkout_request_id
                })
        except Payment.DoesNotExist:
            Payment.objects.create(
                order=order,
                provider='MPESA',
                checkout_request_id=checkout_request_id,
                phone_number=phone_number,
                amount=amount or 0,
                currency=currency,
                status='PENDING'
            )
            logger.info('[process_payment] Created placeholder payment for checkout_request_id=%s', checkout_request_id)
            return JsonResponse({
                'status': 'pending',
                'message': 'Awaiting M-Pesa confirmation',
                'checkout_request_id': checkout_request_id
            })

    # ------------------------------------------------------------------
    #                            PAYPAL
    # ------------------------------------------------------------------
    elif payment_method == 'paypal':
        paypal_order_id = (
            data.get('paypal_order_id')
            or data.get('order_id')
            or data.get('paypalOrderId')
        )
        paypal_payer_id = (
            data.get('paypal_payer_id')
            or data.get('payer_id')
        )

        logger.debug('[process_payment] PayPal data => order=%s payer=%s', paypal_order_id, paypal_payer_id)

        if not paypal_order_id:
            logger.error('[process_payment] Missing PayPal order ID')
            return JsonResponse({'status': 'error', 'message': 'Missing PayPal order ID'}, status=400)

        # Capture PayPal order
        result = capture_paypal_order(paypal_order_id)
        logger.info('[process_payment] PayPal capture result: %s', result)

        if result.get('status', '').upper() == 'COMPLETED':
            payment, _ = Payment.objects.get_or_create(
                order=order,
                provider='PAYPAL',
                defaults={'amount': order.total, 'currency': 'USD', 'status': 'COMPLETED'}
            )
            payment.status = 'COMPLETED'
            payment.transaction_id = result.get('id')
            payment.raw_response = result
            payment.save()

            order.status = 'PAID'
            order.payment_method = 'PAYPAL'
            order.save()
            clear_cart_after_payment(order)

            return JsonResponse({
                'success': True,
                'status': 'success',
                'message': 'PayPal payment completed',
                'transaction_id': result.get('id'),
                'redirect_url': f'/orders/success/{order.id}/'
            })
        else:
            err = result.get('error') or result.get('message') or 'PayPal capture failed'
            logger.error('[process_payment] PayPal capture failed: %s', err)
            return JsonResponse({'status': 'error', 'message': err, 'details': result.get('details')}, status=400)

    # ------------------------------------------------------------------
    #                        INVALID METHOD
    # ------------------------------------------------------------------
    else:
        logger.error('[process_payment] Invalid payment method: %s', payment_method)
        return JsonResponse({'status': 'error', 'message': 'Invalid payment method'}, status=400)



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


def get_or_create_payment(order, provider='PAYPAL', amount=None, currency=None):
    """Safe method to get or create payment without duplicates"""
    try:
        # Try to get existing payment for this order and provider
        payment = Payment.objects.filter(
            order=order,
            provider=provider
        ).latest('created_at')
        return payment, False
    except Payment.DoesNotExist:
        # Create new payment
        payment = Payment.objects.create(
            order=order,
            provider=provider,
            amount=amount or order.total,
            currency=currency or order.currency,
            status='PENDING'
        )
        return payment, True
    except Payment.MultipleObjectsReturned:
        # Handle duplicates by taking the most recent
        payments = Payment.objects.filter(order=order, provider=provider).order_by('-created_at')
        payment = payments.first()
        # Mark older ones as failed
        payments.exclude(id=payment.id).update(
            status='FAILED',
            failure_type='DUPLICATE',
            result_description='Multiple payments detected, using most recent'
        )
        return payment, False

# Update the paypal_checkout function
def paypal_checkout(request, order_id):
    """New PayPal checkout using django-paypal"""
    order = get_object_or_404(Order, id=order_id)

    # What you want the button to do.
    paypal_dict = {
        "business": settings.PAYPAL_RECEIVER_EMAIL,
        "amount": str(order.total),
        "item_name": f"Order #{order.id}",
        "invoice": f"order-{order.id}-{order.created.strftime('%Y%m%d%H%M%S')}",
        "notify_url": request.build_absolute_uri(reverse('paypal-ipn')),
        "return_url": request.build_absolute_uri(
            reverse('orders:success', kwargs={'order_id': order.id})
        ),
        "cancel_return": request.build_absolute_uri(
            reverse('payment:paypal_cancel', kwargs={'order_id': order.id})
        ),
        "custom": json.dumps({
            "order_id": order.id,
            "user_id": request.user.id if request.user.is_authenticated else None
        }),
        "currency_code": order.currency,
    }


    # Create the instance.
    form = PayPalPaymentsForm(initial=paypal_dict)

    # FIXED: Use safe payment creation method
    payment, created = get_or_create_payment(
        order,
        provider='PAYPAL',
        amount=order.total,
        currency=order.currency
    )
    context = {
        "order": order,
        "form": form,
        "paypal_amount": order.total,
        "paypal_currency": order.currency,
    }
    return render(request, "orders/checkout.html", context)


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




@csrf_exempt
@require_http_methods(["POST"])
def mpesa_callback(request):
    """
    Handle M-Pesa STK Push callback
    """
    try:
        # Parse the callback data
        callback_data = json.loads(request.body.decode('utf-8'))
        logger.info(f"[MPESA_CALLBACK] Received callback: {callback_data}")

        # M-Pesa callback structure
        stk_callback = callback_data.get('Body', {}).get('stkCallback', {})
        checkout_request_id = stk_callback.get('CheckoutRequestID')
        result_code = stk_callback.get('ResultCode')
        result_desc = stk_callback.get('ResultDesc')

        logger.info(f"[MPESA_CALLBACK] CheckoutRequestID: {checkout_request_id}, ResultCode: {result_code}")

        if result_code == 0:
            # Payment was successful
            callback_metadata = stk_callback.get('CallbackMetadata', {}).get('Item', [])

            # Extract payment details from metadata
            payment_data = {}
            for item in callback_metadata:
                payment_data[item.get('Name')] = item.get('Value')

            amount = payment_data.get('Amount')
            mpesa_receipt = payment_data.get('MpesaReceiptNumber')
            phone = payment_data.get('PhoneNumber')
            transaction_date = payment_data.get('TransactionDate')

            logger.info(
                f"[MPESA_CALLBACK] Payment successful - Receipt: {mpesa_receipt}, Amount: {amount}, Phone: {phone}")

            # Find and update the payment
            try:
                payment = Payment.objects.get(checkout_request_id=checkout_request_id)
                payment.status = 'completed'
                payment.transaction_id = mpesa_receipt
                payment.phone_number = phone
                payment.amount = amount
                payment.save()

                logger.info(f"[MPESA_CALLBACK] Updated payment {payment.id} with receipt {mpesa_receipt}")

            except Payment.DoesNotExist:
                logger.error(f"[MPESA_CALLBACK] Payment not found for CheckoutRequestID: {checkout_request_id}")
            except Exception as e:
                logger.error(f"[MPESA_CALLBACK] Error updating payment: {str(e)}")

        else:
            # Payment failed
            logger.warning(
                f"[MPESA_CALLBACK] Payment failed - CheckoutRequestID: {checkout_request_id}, Reason: {result_desc}")

            try:
                payment = Payment.objects.get(checkout_request_id=checkout_request_id)
                payment.status = 'failed'
                payment.error_message = result_desc
                payment.save()

                logger.info(f"[MPESA_CALLBACK] Marked payment {payment.id} as failed")
            except Payment.DoesNotExist:
                logger.error(f"[MPESA_CALLBACK] Payment not found for failed CheckoutRequestID: {checkout_request_id}")

        # Return success response to M-Pesa
        response_data = {
            "ResultCode": 0,
            "ResultDesc": "Success"
        }
        return HttpResponse(json.dumps(response_data), content_type='application/json')

    except Exception as e:
        logger.error(f"[MPESA_CALLBACK] Error processing callback: {str(e)}")
        # Still return success to M-Pesa to avoid repeated callbacks
        response_data = {
            "ResultCode": 0,
            "ResultDesc": "Success"
        }
        return HttpResponse(json.dumps(response_data), content_type='application/json')








