from abc import ABC, abstractmethod
import stripe
import requests
from django.conf import settings
from .models import Payment, logger


class BasePaymentProvider(ABC):
    def __init__(self, payment: Payment):
        self.payment = payment

    @abstractmethod
    def initiate_payment(self):
        pass

    @abstractmethod
    def verify_payment(self, verification_data):
        pass

    @abstractmethod
    def process_refund(self, amount):
        pass


class StripeProvider(BasePaymentProvider):
    def __init__(self, payment):
        super().__init__(payment)
        stripe.api_key = settings.STRIPE_SECRET_KEY

    def initiate_payment(self):
        try:
            intent = stripe.PaymentIntent.create(
                amount=int(self.payment.amount * 100),
                currency=self.payment.currency.lower(),
                payment_method_types=['card'],
                metadata={
                    "order_id": self.payment.order.id,
                    "payment_id": self.payment.id
                },
                receipt_email=self.payment.order.user.email,
            )

            return {
                'success': True,
                'client_secret': intent.client_secret,
                'transaction_id': intent.id,
                'gateway_response': intent
            }
        except stripe.error.CardError as e:
            logger.error(f"Stripe card error: {e.error.message}")
            return {
                'success': False,
                'error_code': e.error.code,
                'error_message': e.error.message
            }
        except Exception as e:
            logger.exception("Stripe payment failed")
            return {
                'success': False,
                'error_code': 'STRIPE_ERROR',
                'error_message': str(e)
            }


class MPesaProvider(BasePaymentProvider):
    def __init__(self, payment):
        super().__init__(payment)
        self.access_token = self._get_access_token()

    def _get_access_token(self):
        """Get OAuth token from M-Pesa API"""
        try:
            response = requests.get(
                settings.MPESA_AUTH_URL,
                auth=(settings.MPESA_CONSUMER_KEY, settings.MPESA_CONSUMER_SECRET)
            )
            return response.json().get('access_token')
        except Exception as e:
            logger.error(f"MPesa auth failed: {str(e)}")
            return None

    def initiate_payment(self):
        if not self.access_token:
            return {
                'success': False,
                'error_code': 'AUTH_FAILED',
                'error_message': 'Could not authenticate with payment gateway'
            }

        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }

        payload = {
            "BusinessShortCode": settings.MPESA_SHORTCODE,
            "Password": self._generate_password(),
            "Timestamp": self._get_timestamp(),
            "TransactionType": "CustomerPayBillOnline",
            "Amount": self.payment.amount,
            "PartyA": self.payment.phone_number,
            "PartyB": settings.MPESA_PAYBILL,
            "PhoneNumber": self.payment.phone_number,
            "CallBackURL": settings.MPESA_CALLBACK_URL,
            "AccountReference": f"ORDER{self.payment.order.id}",
            "TransactionDesc": "E-commerce Payment"
        }

        try:
            response = requests.post(
                settings.MPESA_STK_PUSH_URL,
                json=payload,
                headers=headers,
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                return {
                    'success': True,
                    'checkout_request_id': data['CheckoutRequestID'],
                    'merchant_request_id': data['MerchantRequestID'],
                    'gateway_response': data
                }
            else:
                error_msg = response.json().get('errorMessage', 'M-Pesa payment failed')
                return {
                    'success': False,
                    'error_code': 'MPESA_ERROR',
                    'error_message': error_msg
                }
        except Exception as e:
            logger.error(f"MPesa API error: {str(e)}")
            return {
                'success': False,
                'error_code': 'NETWORK_ERROR',
                'error_message': 'Could not connect to payment gateway'
            }

class PayPalProvider(BasePaymentProvider):
    def initiate_payment(self):
        # Actual PayPal implementation would go here
        # This is a simplified version
        return {
            'success': True,
            'redirect_url': 'https://www.paypal.com/checkout/...'
        }

class AirtelMoneyProvider:
    pass


class PaymentProcessor:
    PROVIDERS = {
        'STRIPE': StripeProvider,
        'MPESA': MPesaProvider,
        'AIRTEL': AirtelMoneyProvider,  # Similar to MPesa
        'PAYPAL': PayPalProvider
    }

    def __init__(self, payment: Payment):
        self.payment = payment
        provider_class = self.PROVIDERS.get(payment.method)
        self.provider = provider_class(payment) if provider_class else None

    def process(self):
        if not self.provider:
            return {
                'success': False,
                'error_message': 'Unsupported payment method'
            }

        try:
            result = self.provider.initiate_payment()
            if result:
                return {'success': True, 'data': result}
            return {
                'success': False,
                'error_message': 'Payment initiation failed'
            }
        except Exception as e:
            return {
                'success': False,
                'error_message': str(e)
            }