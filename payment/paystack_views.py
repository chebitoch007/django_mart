# payment/paystack_views.py

import json
import hmac
import hashlib
import logging
from decimal import Decimal
from django.conf import settings
from django.shortcuts import redirect, get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_http_methods
from django.http import JsonResponse, HttpResponse
from django.db import transaction
from django.core.exceptions import ValidationError
from django.urls import reverse
from djmoney.money import Money

from orders.models import Order
from .models import Payment
from .cart_utils import clear_cart_after_payment
from .paystack_utils import (
    initialize_paystack_transaction,
    verify_paystack_transaction,
    is_paystack_currency_supported
)

logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
def initialize_paystack_payment(request):
    """
    Initialize a Paystack payment transaction
    """
    try:
        data = json.loads(request.body)
        order_id = data.get('order_id')
        # Get requested currency, default to settings if missing
        requested_currency = data.get('currency', settings.DEFAULT_CURRENCY)
        requested_amount = data.get('amount')

        if not all([order_id, requested_amount]):
            return JsonResponse({
                'success': False,
                'error': 'Missing required parameters'
            }, status=400)

        # Get order
        order = get_object_or_404(Order, id=order_id)

        if order.status != 'PENDING':
            return JsonResponse({
                'success': False,
                'error': f'Order already {order.status.lower()}'
            }, status=400)

        # --- ✅ CURRENCY HANDLING ---
        # Check if the requested currency is actually supported by Paystack
        if is_paystack_currency_supported(requested_currency):
            # It is supported (e.g., KES), use the values sent from frontend
            final_currency = requested_currency
            final_amount = Decimal(str(requested_amount))
        else:
            # It is NOT supported (e.g., USD if disabled, EUR, GBP)
            # Fallback to the Order's base currency (usually KES) stored in the DB
            logger.info(f"Currency {requested_currency} not supported. Switching to Order Base Currency.")

            # Use 'order.total' directly (DjMoney field)
            total_cost = order.total

            if hasattr(total_cost, 'amount'):
                final_amount = total_cost.amount
                final_currency = str(total_cost.currency)
            else:
                final_amount = Decimal(total_cost)
                final_currency = settings.DEFAULT_CURRENCY

        # Create Money object for the payment record
        try:
            amount_money = Money(final_amount, final_currency)
        except Exception:
            # Fallback if Money fails
            amount_money = Money(Decimal(str(final_amount)), settings.DEFAULT_CURRENCY)

        # Get or create payment record
        from .views import get_or_create_payment_safe
        payment, created = get_or_create_payment_safe(order, 'PAYSTACK', amount_money)

        if not created and payment.status not in ['PENDING', 'FAILED']:
            return JsonResponse({
                'success': False,
                'error': f'Payment already {payment.status.lower()}'
            }, status=400)

        # Initialize transaction with Paystack
        result = initialize_paystack_transaction(
            amount=amount_money,
            email=order.email,
            order_id=order.id,
            metadata={
                'customer_name': order.get_full_name(),
                'phone': order.phone,
                'original_currency': requested_currency  # Track what the user saw
            }
        )

        if result.get('success'):
            # Update payment record
            payment.status = 'PENDING'
            payment.transaction_id = result['reference']
            payment.raw_response = result
            payment.save(update_fields=['status', 'transaction_id', 'raw_response'])

            return JsonResponse({
                'success': True,
                'authorization_url': result['authorization_url'],
                'reference': result['reference'],
                'access_code': result['access_code']
            })
        else:
            error_msg = result.get('error', 'Failed to initialize payment')
            payment.status = 'FAILED'
            payment.failure_type = 'INITIATION_FAILED'
            payment.result_description = error_msg
            payment.save(update_fields=['status', 'failure_type', 'result_description'])

            return JsonResponse({
                'success': False,
                'error': error_msg
            }, status=400)

    except Order.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Order not found'
        }, status=404)

    except Exception as e:
        logger.exception(f"Paystack initialization error: {e}")
        return JsonResponse({
            'success': False,
            'error': 'Failed to initialize payment'
        }, status=500)


@csrf_exempt
def paystack_callback(request):
    """
    Handle Paystack callback after payment (user redirect)
    """
    reference = request.GET.get('reference')

    if not reference:
        logger.error("Paystack callback missing reference")
        return redirect('orders:order_list')

    try:
        # Verify transaction
        result = verify_paystack_transaction(reference)

        if not result.get('success'):
            logger.error(f"Paystack verification failed: {result.get('error')}")
            return redirect('orders:order_list')

        # Get payment record
        payment = Payment.objects.filter(
            transaction_id=reference,
            provider='PAYSTACK'
        ).first()

        if not payment:
            logger.error(f"Payment not found for reference: {reference}")
            return redirect('orders:order_list')

        order = payment.order

        # Check transaction status
        if result['status'] == 'success':
            with transaction.atomic():
                payment = Payment.objects.select_for_update().get(pk=payment.pk)

                if payment.status == 'COMPLETED':
                    logger.info(f"Payment {payment.id} already completed")
                    return redirect('orders:success', order_id=order.id)

                # Update payment
                payment.status = 'COMPLETED'
                payment.raw_response = result
                payment.save(update_fields=['status', 'raw_response'])

                # Mark order as paid
                try:
                    if order.status == 'PENDING':
                        order.mark_as_paid(payment_method='PAYSTACK')
                        clear_cart_after_payment(order)
                        logger.info(f"Order {order.id} marked as PAID via Paystack")
                except (ValidationError, PermissionError) as e:
                    logger.warning(f"Order {order.id} already processed: {e}")

            return redirect('orders:success', order_id=order.id)

        else:
            # Payment failed
            payment.status = 'FAILED'
            payment.failure_type = 'PAYMENT_FAILED'
            payment.result_description = f"Transaction status: {result['status']}"
            payment.save(update_fields=['status', 'failure_type', 'result_description'])

            return redirect('orders:order_detail', pk=order.id)

    except Exception as e:
        logger.exception(f"Paystack callback error: {e}")
        return redirect('orders:order_list')


@csrf_exempt
@require_http_methods(["POST"])
def paystack_webhook(request):
    """
    Handle Paystack webhook events
    """
    # Verify webhook signature
    signature = request.META.get('HTTP_X_PAYSTACK_SIGNATURE')

    if not signature:
        logger.warning("Paystack webhook missing signature")
        return HttpResponse(status=400)

    # Compute HMAC signature
    computed_signature = hmac.new(
        settings.PAYSTACK_SECRET_KEY.encode('utf-8'),
        request.body,
        hashlib.sha512
    ).hexdigest()

    if signature != computed_signature:
        logger.warning("Paystack webhook signature verification failed")
        return HttpResponse(status=400)

    try:
        payload = json.loads(request.body)
        event = payload.get('event')
        data = payload.get('data', {})

        logger.info(f"Paystack webhook event: {event}")

        # Handle different event types
        if event == 'charge.success':
            return handle_charge_success(data)

        elif event == 'charge.failed':
            return handle_charge_failed(data)

        elif event == 'transfer.success':
            return handle_transfer_success(data)

        elif event == 'transfer.failed':
            return handle_transfer_failed(data)

        else:
            logger.info(f"Ignoring Paystack webhook event: {event}")
            return HttpResponse(status=200)

    except json.JSONDecodeError:
        logger.error("Invalid JSON in Paystack webhook")
        return HttpResponse(status=400)

    except Exception as e:
        logger.exception("Error processing Paystack webhook")
        return HttpResponse(status=500)


def handle_charge_success(data):
    """Handle successful charge webhook"""
    try:
        reference = data.get('reference')

        if not reference:
            logger.error("Charge success webhook missing reference")
            return HttpResponse(status=400)

        with transaction.atomic():
            payment = Payment.objects.select_for_update().filter(
                transaction_id=reference,
                provider='PAYSTACK'
            ).first()

            if not payment:
                logger.error(f"Payment not found for reference: {reference}")
                return HttpResponse(status=44)

            if payment.status == 'COMPLETED':
                logger.info(f"Payment {payment.id} already completed")
                return HttpResponse(status=200)

            # Update payment
            payment.status = 'COMPLETED'
            payment.raw_response = data
            payment.save(update_fields=['status', 'raw_response'])

            # Update order
            order = payment.order
            try:
                if order.status == 'PENDING':
                    order.mark_as_paid(payment_method='PAYSTACK')
                    clear_cart_after_payment(order)
                    logger.info(f"Order {order.id} marked as PAID via Paystack webhook")
            except (ValidationError, PermissionError) as e:
                logger.warning(f"Order {order.id} already processed: {e}")

        return HttpResponse(status=200)

    except Exception as e:
        logger.exception("Error handling charge success")
        return HttpResponse(status=500)


def handle_charge_failed(data):
    """Handle failed charge webhook"""
    try:
        reference = data.get('reference')

        if not reference:
            logger.error("Charge failed webhook missing reference")
            return HttpResponse(status=400)

        payment = Payment.objects.filter(
            transaction_id=reference,
            provider='PAYSTACK'
        ).first()

        if payment:
            payment.status = 'FAILED'
            payment.failure_type = 'PAYMENT_FAILED'
            payment.result_description = data.get('gateway_response', 'Payment failed')
            payment.raw_response = data
            payment.save()
            logger.info(f"Payment {payment.id} marked as FAILED")

        return HttpResponse(status=200)

    except Exception as e:
        logger.exception("Error handling charge failed")
        return HttpResponse(status=500)


def handle_transfer_success(data):
    """Handle successful transfer (for refunds)"""
    logger.info(f"Transfer success: {data.get('reference')}")
    return HttpResponse(status=200)


def handle_transfer_failed(data):
    """Handle failed transfer"""
    logger.warning(f"Transfer failed: {data.get('reference')}")
    return HttpResponse(status=200)


@csrf_exempt
@require_POST
def paystack_status(request):
    """
    Check Paystack payment status.
    Verifies status with Paystack if local status is PENDING.
    """
    try:
        if not request.body:
            return JsonResponse({'status': 'error', 'message': 'Empty body'}, status=400)

        data = json.loads(request.body)
        reference = data.get('reference')

        if not reference:
            return JsonResponse({'status': 'error', 'message': 'No reference'}, status=400)

        payment = Payment.objects.get(
            transaction_id=reference,
            provider='PAYSTACK'
        )

        # Verify with Paystack if pending
        if payment.status == 'PENDING':
            try:
                logger.info(f"[Paystack] Actively verifying pending payment: {reference}")
                result = verify_paystack_transaction(reference)

                if result.get('success'):
                    upstream_status = result.get('status')

                    # Map Paystack status to our system
                    if upstream_status == 'success':
                        with transaction.atomic():
                            payment.status = 'COMPLETED'
                            payment.raw_response = result
                            payment.save()

                            order = payment.order
                            if order.status == 'PENDING':
                                order.mark_as_paid(payment_method='PAYSTACK')
                                clear_cart_after_payment(order)
                                logger.info(f"Order {order.id} marked as PAID via active verification")

                    elif upstream_status in ['abandoned', 'failed', 'reversed']:
                        payment.status = 'FAILED'
                        payment.failure_type = 'PAYMENT_FAILED' if upstream_status == 'failed' else 'USER_CANCELLED'
                        payment.result_description = f"Paystack status: {upstream_status}"
                        payment.save()
                        logger.info(f"Payment {payment.id} marked as {payment.status} (Paystack: {upstream_status})")

            except Exception as e:
                logger.error(f"[Paystack] Active verification error: {e}")

        return JsonResponse({
            'status': payment.status.lower(),
            'reference': payment.transaction_id,
            'order_id': payment.order.id,
            'amount': str(payment.amount),
            'currency': payment.amount.currency.code
        })

    except Payment.DoesNotExist:
        return JsonResponse({
            'status': 'not_found',
            'message': 'Payment not found'
        }, status=404)

    except Exception as e:
        logger.error(f"Error checking Paystack status: {e}")
        return JsonResponse({
            'status': 'error',
            'message': 'Internal server error'
        }, status=500)