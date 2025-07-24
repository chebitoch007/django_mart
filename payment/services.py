

import requests
from celery import result
from django.urls import reverse
from .providers import StripeProvider, MPesaProvider, PayPalProvider

from decimal import Decimal
from .models import CurrencyExchangeRate

import logging
from django.conf import settings
from .models import Payment

import paypalrestsdk

logger = logging.getLogger(__name__)


class PaymentProcessor:
    def __init__(self, payment, **kwargs):
        self.payment = payment
        self.order = payment.order
        self.method = kwargs.get('method')
        self.amount = payment.amount
        self.currency = payment.currency
        self.user = payment.order.user
        self.payment_method = payment.payment_method
        self.idempotency_key = kwargs.get('idempotency_key')

    def process(self):
        logger.info(f"Processing payment for order {self.order.id}")

        # Idempotency check
        if self.idempotency_key:
            if Payment.objects.filter(idempotency_key=self.idempotency_key).exists():
                logger.warning(f"Duplicate idempotency key: {self.idempotency_key}")
                return {
                    'success': False,
                    'error_code': 'DUPLICATE_REQUEST',
                    'error_message': 'This payment has already been processed'
                }

        # Assign idempotency key before calling gateway
        if self.idempotency_key:
            self.payment.idempotency_key = self.idempotency_key
            self.payment.save(update_fields=['idempotency_key'])

        try:
            # Route to appropriate payment method
            if self.method in ['MPESA', 'AIRTEL']:
                result = self.process_mobile_money()
            elif self.method in ['VISA', 'MASTERCARD']:
                result = self.process_card()
            elif self.method == 'PAYPAL':
                result = self.process_paypal()
            else:
                result = self.error_result("Unsupported payment method")

        except Exception as exc:
            logger.exception("Error during payment processing", exc_info=exc)
            return self.error_result("System error")

        logger.info(f"Payment result for order {self.payment.order.id}: {result}")
        return result

    def process_mobile_money(self):
        """Process mobile money payment with actual API"""
        provider = MPesaProvider(self.payment)
        result = provider.initiate_payment()

        if result.get('success'):
            self.payment.gateway_response = result.get('gateway_response')
            self.payment.gateway_transaction_id = result.get('transaction_id')
            self.payment.status = 'PROCESSING'
            self.payment.save()

            # Set payment deadline
            self.payment.set_payment_deadline(hours=24)

            return {
                'success': True,
                'verification_required': True,
                'gateway_data': result
            }
        else:
            self.payment.mark_as_failed(
                error_code=result.get('error_code'),
                error_message=result.get('error_message')
            )
            return result

    def process_card(self):
        """Process card payment with Stripe"""
        provider = StripeProvider(self.payment)
        result = provider.initiate_payment()

        if result.get('success'):
            self.payment.mark_as_paid()
            return {
                'success': True,
                'gateway_data': result
            }
        else:
            self.payment.mark_as_failed(
                error_code=result.get('error_code'),
                error_message=result.get('error_message')
            )
            return result

    def process_paypal(self):
        """Process PayPal payment"""
        provider = PayPalProvider(self.payment)
        result = provider.initiate_payment()

        if result.get('success'):
            self.payment.mark_as_paid()
            return {'success': True, 'gateway_data': result}
        else:
            self.payment.mark_as_failed(
                error_code=result.get('error_code'),
                error_message=result.get('error_message')
            )
            return result

    def error_result(self, message, code="PAYMENT_FAILED"):
        return {
            'success': False,
            'error_code': code,
            'error_message': message
        }

    def get_live_exchange_rate(from_curr, to_curr):
        """Fetch live rates from external API"""
        try:
            # Using free API (replace with your preferred service)
            response = requests.get(
                f"https://api.exchangerate-api.com/v4/latest/{from_curr}",
                timeout=3
            )
            data = response.json()
            return data['rates'].get(to_curr)
        except Exception as e:
            logger.error(f"Exchange rate API error: {str(e)}")
            return None


def convert_currency(amount, from_currency, to_currency):
    if from_currency == to_currency:
        return amount

    # Try to get the latest exchange rate
    rate = CurrencyExchangeRate.objects.filter(
        base_currency=from_currency,
        target_currency=to_currency
    ).order_by('-last_updated').first()

    if rate:
        return amount * rate.rate

    # Fallback to settings if no rate in DB
    fallback_rates = settings.CURRENCY_FALLBACK_RATES
    key = f"{from_currency}_{to_currency}"
    if key in fallback_rates:
        return amount * Decimal(str(fallback_rates[key]))

    # If no rate found, return original amount (should not happen in production)
    return amount


def get_currency_options():
    return [
        {'code': 'KES', 'name': 'Kenyan Shilling'},
        {'code': 'USD', 'name': 'US Dollar'},
        {'code': 'EUR', 'name': 'Euro'},
        {'code': 'GBP', 'name': 'British Pound'},
    ]

class PayPalService:
    def __init__(self):
        self.api = paypalrestsdk.Api({
            'mode': 'sandbox' if settings.PAYPAL_TEST else 'live',
            'client_id': settings.PAYPAL_CLIENT_ID,
            'client_secret': settings.PAYPAL_SECRET
        })

    def create_payment(self, payment):
        """Create PayPal payment"""
        return self.api.Payment({
            "intent": "sale",
            "payer": {"payment_method": "paypal"},
            "transactions": [{
                "amount": {
                    "total": str(payment.amount),
                    "currency": payment.currency
                },
                "description": f"Payment for Order #{payment.order.id}"
            }],
            "redirect_urls": {
                "return_url": settings.SITE_URL + reverse('payment:paypal-execute'),
                "cancel_url": settings.SITE_URL + reverse('payment:paypal-cancel')
            }
        })

    def execute_payment(self, payment_id, payer_id):
        """Execute approved PayPal payment"""
        payment = self.api.Payment.find(payment_id)
        return payment.execute({"payer_id": payer_id})