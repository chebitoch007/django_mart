#payment/utils.py

from django.core.cache import cache
from django.urls import reverse
from django.utils import timezone
from decimal import Decimal, ROUND_HALF_UP
from djmoney.money import Money
import time
from datetime import datetime
import base64
import requests
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


# -----------------------------
# PAYPAL CLIENT
# -----------------------------
class PayPalClient:
    """High-end PayPal API client with connection pooling and retry logic"""

    def __init__(self):
        self.api_url = settings.PAYPAL_API_URL
        self.client_id = settings.PAYPAL_CLIENT_ID
        self.secret = settings.PAYPAL_SECRET
        self.timeout = 30
        self.max_retries = 3
        self.retry_delay = 1

    def _get_access_token(self):
        """Get cached access token with automatic refresh"""
        cache_key = f'paypal_access_token_{self.client_id}'
        token = cache.get(cache_key)

        if token:
            return token
        try:
            auth = (self.client_id, self.secret)
            data = {'grant_type': 'client_credentials'}
            headers = {
                'Accept': 'application/json',
                'Accept-Language': 'en_US'
            }

            response = requests.post(
                f"{self.api_url}/v1/oauth2/token",
                auth=auth,
                data=data,
                headers=headers,
                timeout=10
            )
            response.raise_for_status()

            token_data = response.json()
            token = token_data['access_token']
            expires_in = token_data.get('expires_in', 3600) - 300  # 5 min buffer

            cache.set(cache_key, token, expires_in)
            logger.info("PayPal access token refreshed successfully")
            return token

        except requests.exceptions.RequestException as e:
            logger.error(f"PayPal auth failed: {str(e)}")
            raise Exception(f"PayPal service unavailable: {str(e)}")

    def _make_request(self, method, endpoint, data=None, retry_count=0):
        """Make API request with retry logic and proper error handling"""
        try:
            url = f"{self.api_url}{endpoint}"
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {self._get_access_token()}',
                'Prefer': 'return=representation'
            }

            response = requests.request(
                method,
                url,
                json=data,
                headers=headers,
                timeout=self.timeout
            )

            if response.status_code == 401 and retry_count < self.max_retries:
                cache_key = f'paypal_access_token_{self.client_id}'
                cache.delete(cache_key)
                return self._make_request(method, endpoint, data, retry_count + 1)

            response.raise_for_status()
            return response.json()

        except requests.exceptions.Timeout:
            if retry_count < self.max_retries:
                timezone.sleep(self.retry_delay * (2 ** retry_count))
                return self._make_request(method, endpoint, data, retry_count + 1)
            raise Exception("PayPal API timeout - please try again")

        except requests.exceptions.RequestException as e:
            logger.error(f"PayPal API error: {str(e)}")
            raise Exception(f"Payment service temporarily unavailable")


paypal_client = PayPalClient()


# -----------------------------
# PAYPAL INTEGRATION
# -----------------------------
def create_paypal_order(amount, currency, order_id, request=None):
    """Create a PayPal order, supporting both Money and numeric types"""
    try:
        # --- Normalize amount ---
        if isinstance(amount, Money):
            currency = amount.currency.code
            amount = amount.amount

        if not isinstance(amount, (Decimal, float, int)):
            raise ValueError("Amount must be numeric or a Money object")

        if amount <= 0:
            raise ValueError("Amount must be positive")

        # Format amount to 2 decimal places
        amount_decimal = Decimal(str(amount)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        # --- Validate currency ---
        if not is_paypal_currency_supported(currency):
            logger.warning(f"Unsupported currency {currency}, defaulting to USD.")
            currency = 'USD'

        # --- User IP for fraud detection ---
        user_ip = None
        if request:
            user_ip = request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0] or request.META.get('REMOTE_ADDR')

        payload = {
            "intent": "CAPTURE",
            "purchase_units": [{
                "reference_id": f"ORDER_{order_id}",
                "description": f"Payment for Order #{order_id}",
                "custom_id": str(order_id),
                "amount": {
                    "currency_code": currency,
                    "value": f"{amount_decimal:.2f}",
                    "breakdown": {
                        "item_total": {
                            "currency_code": currency,
                            "value": f"{amount_decimal:.2f}"
                        }
                    }
                },
                "items": [{
                    "name": f"Order #{order_id}",
                    "description": "Store purchase",
                    "quantity": "1",
                    "unit_amount": {
                        "currency_code": currency,
                        "value": f"{amount_decimal:.2f}"
                    }
                }]
            }],
            "application_context": {
                "brand_name": getattr(settings, "PAYPAL_BRAND_NAME", "ASAI Store"),
                "locale": "en-US",
                "landing_page": "BILLING",
                "shipping_preference": "NO_SHIPPING",
                "user_action": "PAY_NOW",
                "return_url": f"{settings.BASE_URL}/payment/paypal/return/{order_id}/",
                "cancel_url": f"{settings.BASE_URL}/payment/paypal/cancel/{order_id}/"
            }
        }

        if user_ip:
            payload['application_context']['payer'] = {'ip_address': user_ip}

        result = paypal_client._make_request('POST', '/v2/checkout/orders', payload)
        logger.info(f"PayPal order created successfully: {result.get('id')}")
        return result

    except Exception as e:
        logger.exception(f"PayPal order creation failed: {e}")
        return {'error': 'Failed to create payment order', 'details': str(e)}


def capture_paypal_order(order_id):
    try:
        result = paypal_client._make_request('POST', f'/v2/checkout/orders/{order_id}/capture')
        logger.info(f"PayPal order captured: {order_id}")
        return result
    except Exception as e:
        logger.error(f"PayPal capture failed for {order_id}: {str(e)}")
        return {'error': 'Payment capture failed', 'details': str(e)}


def get_paypal_order_details(order_id):
    try:
        result = paypal_client._make_request('GET', f'/v2/checkout/orders/{order_id}')
        return result
    except Exception as e:
        logger.error(f"Failed to get PayPal order details: {str(e)}")
        return None


def is_paypal_currency_supported(currency):
    """Check if currency is supported by PayPal"""
    supported = {
        'USD', 'EUR', 'GBP', 'CAD', 'AUD', 'JPY', 'CHF', 'HKD', 'SGD',
        'SEK', 'DKK', 'PLN', 'NOK', 'HUF', 'CZK', 'ILS', 'MXN', 'NZD',
        'BRL', 'PHP', 'TWD', 'THB', 'TRY', 'RUB', 'CNY', 'INR', 'MYR'
    }
    return currency.upper() in supported


# -----------------------------
# MPESA INTEGRATION
# -----------------------------
def initiate_mpesa_payment(amount, phone_number, order_id):
    """Initiate M-Pesa STK push payment with support for Money and numeric types"""
    try:
        # --- Normalize Money objects ---
        if isinstance(amount, Money):
            amount_value = amount.amount
        else:
            amount_value = amount

        # --- Validate amount ---
        try:
            amount_float = float(amount_value)
            if amount_float <= 0:
                return {'errorMessage': 'Invalid amount. Amount must be greater than 0.'}
            amount_int = int(round(amount_float))
        except (ValueError, TypeError):
            return {'errorMessage': 'Invalid amount format'}

        # --- Authentication ---
        max_retries = 3
        access_token = None

        for attempt in range(max_retries):
            try:
                auth_url = "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
                auth_response = requests.get(
                    auth_url,
                    auth=(settings.MPESA_CONSUMER_KEY, settings.MPESA_CONSUMER_SECRET),
                    timeout=10,
                    headers={'Accept': 'application/json'}
                )
                auth_response.raise_for_status()
                access_token = auth_response.json().get('access_token')
                break
            except requests.exceptions.RequestException as e:
                logger.error(f"M-Pesa auth error (attempt {attempt + 1}): {str(e)}")
                if attempt == max_retries - 1:
                    return {'errorMessage': 'M-Pesa service temporarily unavailable'}
                time.sleep(3)

        if not access_token:
            return {'errorMessage': 'Failed to get access token'}

        # --- Format phone number ---
        if phone_number.startswith('0'):
            phone_number = '254' + phone_number[1:]
        elif not phone_number.startswith('254'):
            phone_number = '254' + phone_number

        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        password = base64.b64encode(
            f"{settings.MPESA_SHORTCODE}{settings.MPESA_PASSKEY}{timestamp}".encode()
        ).decode()

        callback_url = f"{settings.BASE_URL}{reverse('payment:payment_webhook', args=['MPESA'])}"
        if not callback_url.endswith('/'):
            callback_url += '/'

        payload = {
            "BusinessShortCode": settings.MPESA_SHORTCODE,
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": amount_int,
            "PartyA": phone_number,
            "PartyB": settings.MPESA_SHORTCODE,
            "PhoneNumber": phone_number,
            "CallBackURL": callback_url,
            "AccountReference": f"ORDER_{order_id}",
            "TransactionDesc": "ASAI Payment"
        }

        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
        }

        logger.info(f"[M-Pesa] Initiating payment: {amount_int} KES to {phone_number} for order {order_id}")

        response = requests.post(
            "https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest",
            json=payload,
            headers=headers,
            timeout=15
        )
        result = response.json()

        if 'ResponseCode' in result and result.get('ResponseCode') == '0':
            logger.info(f"M-Pesa payment initiated successfully: {result.get('CheckoutRequestID')}")
            return result
        else:
            error_msg = result.get('errorMessage') or result.get('ResponseDescription') or 'M-Pesa payment failed'
            logger.error(f"M-Pesa payment failed: {error_msg}")
            return {'errorMessage': error_msg}

    except Exception as e:
        logger.error(f"M-Pesa initiation error: {str(e)}")
        return {'errorMessage': 'Failed to initiate M-Pesa payment'}


# -----------------------------
# HELPERS
# -----------------------------
def is_currency_supported(currency, provider):
    """Check if a currency is supported by a payment provider"""
    if provider == 'PAYPAL':
        return is_paypal_currency_supported(currency)
    elif provider == 'MPESA':
        return True  # all currencies converted to KES
    return False


def get_prioritized_payment_methods(request):
    """Prioritize M-Pesa in Kenya, otherwise PayPal first"""
    country = getattr(request, 'country', None)
    if country == 'KE':
        return ['mpesa', 'paypal']
    return ['paypal', 'mpesa']
