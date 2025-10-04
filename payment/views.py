from datetime import timedelta

from django.urls import reverse

from paypal.standard.forms import PayPalPaymentsForm

import json

from decimal import Decimal

import requests

from django.conf import settings

from core.utils import get_exchange_rate, logger

from django.shortcuts import get_object_or_404, render, redirect

from django.http import JsonResponse

from django.views.decorators.csrf import csrf_exempt

from django.views.decorators.http import require_POST

from django.utils import timezone

from orders.models import Order

from .models import Payment

from .utils import initiate_mpesa_payment, create_paypal_order, is_currency_supported, capture_paypal_order, is_paypal_currency_supported

from .webhooks import handle_mpesa_webhook, handle_paypal_webhook



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

    """FIXED: Enhanced M-Pesa status polling with webhook acceptance"""

    checkout_request_id = request.GET.get('checkout_request_id')



    if not checkout_request_id:

        return JsonResponse({

            'status': 'error',

            'message': 'checkout_request_id is required'

        }, status=400)



    try:

        payment = Payment.objects.get(

            checkout_request_id=checkout_request_id,

            provider='MPESA'

        )



        # ✅ FIX: Only timeout if we haven't received a webhook

        if payment.status == 'PROCESSING':

            processing_time = timezone.now() - payment.created_at

            timeout_threshold = timedelta(minutes=20)  # Increased to 20 minutes



            # Auto-timeout after 20 minutes ONLY if no webhook received

            if processing_time > timeout_threshold and not payment.raw_callback:

                payment.status = 'FAILED'

                payment.failure_type = 'TIMEOUT'

                payment.result_description = 'Payment timeout after 20 minutes - no callback received'

                payment.save()

                logger.info(f"Payment {payment.id} timed out after 20 minutes (no webhook)")

            elif processing_time > timeout_threshold and payment.raw_callback:

                # Webhook received but status not updated - process the webhook data

                logger.info(f"Webhook received but status not updated for payment {payment.id}")

                # The status will be updated by the next webhook processing



        response_data = {

            'status': payment.status.lower(),

            'failure_type': payment.failure_type,

            'message': payment.result_description or f"Payment {payment.status.lower()}",

            'result_code': payment.result_code,

            'result_description': payment.result_description,

            'amount': str(payment.amount),

            'order_id': payment.order.id,

            'transaction_id': payment.transaction_id,

            'can_retry': payment.failure_type in ['TEMPORARY', 'USER_CANCELLED', 'TIMEOUT'] and

                         (payment.failure_type != 'TEMPORARY' or payment.retry_count < 3),

            'retry_count': payment.retry_count,

            'webhook_received': bool(payment.raw_callback)  # Add this for debugging

        }



        return JsonResponse(response_data)



    except Payment.DoesNotExist:

        logger.error(f"No payment found for checkout_request_id: {checkout_request_id}")

        return JsonResponse({

            'status': 'not_found',

            'message': 'No payment found for this checkout_request_id'

        }, status=404)

    except Exception as e:

        logger.error(f"Error checking payment status: {str(e)}")

        return JsonResponse({

            'status': 'error',

            'message': 'Error checking payment status'

        }, status=500)





@csrf_exempt

def initiate_payment(request):

    """FIXED: Payment initiation with duplicate prevention"""

    if request.method != 'POST':

        return JsonResponse({'success': False, 'error': 'Invalid request method'}, status=405)



    try:

        data = json.loads(request.body)

        order_id = data.get('order_id')

        provider = data.get('provider')

        phone = data.get('phone')

        amount = data.get('amount')

        currency = data.get('currency')



        if not all([order_id, provider, amount, currency]):

            return JsonResponse({'success': False, 'error': 'Missing required parameters'}, status=400)



        order = get_object_or_404(Order, id=order_id)



        # ✅ FIXED: Use safe payment method

        if provider == 'MPESA':

            payment, created = get_or_create_payment_safe(order, 'MPESA', amount, currency)

        elif provider == 'PAYPAL':

            return JsonResponse({

                'success': False,

                'error': 'Use /payment/paypal/create/ endpoint for PayPal payments',

                'redirect': True

            }, status=400)

        else:

            return JsonResponse({

                'success': False,

                'error': 'Invalid payment provider'

            })



        if provider == 'MPESA':

            # Currency conversion for M-Pesa (always uses KES)

            original_currency = currency

            original_amount = Decimal(amount)



            if original_currency != 'KES':

                exchange_rate = get_exchange_rate(original_currency, 'KES')

                converted_amount = (original_amount * exchange_rate).quantize(Decimal('0.01'))

                payment.original_amount = original_amount

                payment.original_currency = original_currency

                payment.converted_amount = converted_amount

                payment.exchange_rate = exchange_rate

                payment.currency = 'KES'

                amount_to_use = converted_amount

            else:

                payment.original_amount = original_amount

                payment.original_currency = original_currency

                payment.converted_amount = None

                payment.exchange_rate = None

                amount_to_use = original_amount



            # M-Pesa processing

            result = initiate_mpesa_payment(amount_to_use, phone, order_id)



            if result.get('ResponseCode') == '0':

                payment.status = 'PROCESSING'

                payment.provider = 'MPESA'

                payment.phone_number = phone

                payment.raw_response = result

                payment.checkout_request_id = result.get('CheckoutRequestID')

                payment.save()



                return JsonResponse({

                    'success': True,

                    'checkout_request_id': result.get('CheckoutRequestID'),

                    'converted_amount': str(amount_to_use) if original_currency != 'KES' else None,

                    'exchange_rate': str(exchange_rate) if original_currency != 'KES' else None,

                    'message': 'M-Pesa payment initiated successfully'

                })

            else:

                return JsonResponse({

                    'success': False,

                    'error': result.get('errorMessage', 'M-Pesa payment failed')

                })



    except json.JSONDecodeError:

        return JsonResponse({

            'success': False,

            'error': 'Invalid JSON data'

        }, status=400)

    except Exception as e:

        logger.error(f'Payment initiation failed: {str(e)}')

        return JsonResponse({

            'success': False,

            'error': f'Payment initiation failed: {str(e)}'

        })







@csrf_exempt

def payment_webhook(request, provider):

    if provider == 'MPESA':

        return handle_mpesa_webhook(request)

    elif provider == 'PAYPAL':

        return handle_paypal_webhook(request)

    return JsonResponse({'error': 'Invalid provider'}, status=400)





@require_POST

def process_payment(request, order_id):

    try:

        order = get_object_or_404(Order, id=order_id)

        payment_method = request.POST.get('payment_method')

        checkout_request_id = request.POST.get('checkout_request_id')

        phone_number = request.POST.get('phone_number')

        amount = request.POST.get('amount')

        currency = request.POST.get('currency', 'KES')



        # Get or create payment

        payment, created = Payment.objects.get_or_create(

            order=order,

            defaults={

                'amount': amount,

                'currency': currency,

                'status': 'PENDING'

            }

        )



        if payment_method == 'mpesa':

            # For M-Pesa, check if payment is already completed via webhook

            if payment.status == 'COMPLETED':

                order.status = 'PAID'

                order.save()



                return JsonResponse({

                    'status': 'success',

                    'message': 'Payment already completed',

                    'redirect_url': f'/orders/success/{order.id}/'

                })

            else:

                if checkout_request_id:

                    try:

                        payment_obj = Payment.objects.get(

                            checkout_request_id=checkout_request_id,

                            provider='MPESA'

                        )

                        return JsonResponse({

                            'status': payment_obj.status.lower(),

                            'failure_type': payment_obj.failure_type,

                            'result_description': payment_obj.result_description,

                            'can_retry': payment_obj.failure_type in ['TEMPORARY', 'USER_CANCELLED', 'TIMEOUT'] and

                                        (payment_obj.failure_type != 'TEMPORARY' or payment_obj.retry_count < 3)

                        })

                    except Payment.DoesNotExist:

                        return JsonResponse({'status': 'error', 'message': 'Payment not found'})

                else:

                    return JsonResponse({'status': 'error', 'message': 'Missing checkout request ID'})



        elif payment_method == 'paypal':

            paypal_order_id = request.POST.get('paypal_order_id')

            if not paypal_order_id:

                return JsonResponse({'status': 'error', 'message': 'Missing PayPal order ID'}, status=400)



            # Capture the PayPal order

            result = capture_paypal_order(paypal_order_id)



            if result.get('status') == 'COMPLETED':

                payment.status = 'COMPLETED'

                payment.transaction_id = result.get('id')

                payment.raw_response = result

                payment.provider = 'PAYPAL'

                payment.save()



                order.status = 'PAID'

                order.payment_method = 'PAYPAL'

                order.save()



                # ✅ Clear cart after successful PayPal payment

                from .views import clear_cart_after_payment

                clear_cart_after_payment(order)



                return JsonResponse({

                    'status': 'success',

                    'message': 'PayPal payment completed successfully',

                    'transaction_id': result.get('id'),

                    'redirect_url': f'/orders/success/{order.id}/'

                })

            else:

                error_msg = result.get('message', 'PayPal payment capture failed')

                return JsonResponse({

                    'status': 'error',

                    'message': error_msg,

                    'details': result.get('details')

                }, status=400)



        else:

            return JsonResponse({'status': 'error', 'message': 'Invalid payment method'})



    except Exception as e:

        logger.error(f'Payment processing error: {str(e)}')

        return JsonResponse({

            'status': 'error',

            'message': f'Payment processing failed: {str(e)}'

        }, status=500)







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







# ✅ ADD CART CLEARING FUNCTION

def clear_cart_after_payment(order):

    """Clear user's cart after successful payment"""

    try:

        from cart.models import Cart

        if order.user and order.user.is_authenticated:

            # Clear user's cart

            user_carts = Cart.objects.filter(user=order.user)

            if user_carts.exists():

                cart = user_carts.first()

                item_count = cart.items.count()

                cart.clear()

                logger.info(f"Cleared cart for user {order.user.id}: {item_count} items removed after order {order.id}")

                return True

        logger.info(f"No cart to clear for order {order.id}")

        return False

    except Exception as e:

        logger.error(f"Error clearing cart: {str(e)}")

        return False



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