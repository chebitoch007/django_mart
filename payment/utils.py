#payment/utils.py

from django.core.cache import cache
from django.utils import timezone
from decimal import Decimal, ROUND_HALF_UP
import time
from datetime import datetime
import base64
import requests
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


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
                # Token might be expired, clear cache and retry
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


def create_paypal_order(amount, currency, order_id, request=None):
    """Create a PayPal order with enhanced error handling and validation"""
    try:
        # Validate inputs
        if not isinstance(amount, (Decimal, float, int)):
            raise ValueError("Amount must be numeric")

        if amount <= 0:
            raise ValueError("Amount must be positive")

        # Format amount to 2 decimal places
        amount_decimal = Decimal(str(amount)).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )

        # Get user IP for fraud detection
        user_ip = request.META.get('HTTP_X_FORWARDED_FOR') if request else None
        if not user_ip and request:
            user_ip = request.META.get('REMOTE_ADDR')

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
                "brand_name": settings.PAYPAL_BRAND_NAME or "ASAI Store",
                "locale": "en-US",
                "landing_page": "BILLING",
                "shipping_preference": "NO_SHIPPING",
                "user_action": "PAY_NOW",
                "return_url": f"{settings.BASE_URL}/payment/paypal/return/{order_id}/",
                "cancel_url": f"{settings.BASE_URL}/payment/paypal/cancel/{order_id}/"
            }
        }
        # Add fraud detection headers if IP available
        if user_ip:
            payload['application_context']['payer'] = {
                'ip_address': user_ip.split(',')[0]  # First IP in chain
            }

        logger.info(f"Creating PayPal order for {amount_decimal} {currency}, order: {order_id}")

        result = paypal_client._make_request(
            'POST',
            '/v2/checkout/orders',
            payload
        )

        logger.info(f"PayPal order created: {result.get('id')}")
        return result

    except ValueError as e:
        logger.error(f"PayPal order validation error: {str(e)}")
        return {'error': 'Invalid payment parameters', 'details': str(e)}
    except Exception as e:
        logger.error(f"PayPal order creation failed: {str(e)}")
        return {'error': 'Failed to create payment order', 'details': str(e)}


def capture_paypal_order(order_id):
    """Capture a PayPal payment after user approval"""
    try:
        result = paypal_client._make_request(
            'POST',
            f'/v2/checkout/orders/{order_id}/capture'
        )

        logger.info(f"PayPal order captured: {order_id}")
        return result

    except Exception as e:
        logger.error(f"PayPal capture failed for {order_id}: {str(e)}")
        return {'error': 'Payment capture failed', 'details': str(e)}


def get_paypal_order_details(order_id):
    """Get detailed information about a PayPal order"""
    try:
        result = paypal_client._make_request(
            'GET',
            f'/v2/checkout/orders/{order_id}'
        )
        return result
    except Exception as e:
        logger.error(f"Failed to get PayPal order details: {str(e)}")
        return None


def is_paypal_currency_supported(currency):
    """Check if currency is supported by PayPal with enhanced list"""
    supported_currencies = {
        'USD', 'EUR', 'GBP', 'CAD', 'AUD', 'JPY', 'CHF', 'HKD', 'SGD',
        'SEK', 'DKK', 'PLN', 'NOK', 'HUF', 'CZK', 'ILS', 'MXN', 'NZD',
        'BRL', 'PHP', 'TWD', 'THB', 'TRY', 'RUB', 'CNY', 'INR', 'MYR'
    }
    return currency.upper() in supported_currencies




def get_paypal_access_token():
    """Get PayPal access token for API requests"""
    auth = (settings.PAYPAL_CLIENT_ID, settings.PAYPAL_SECRET)
    data = {'grant_type': 'client_credentials'}
    headers = {'Accept': 'application/json'}

    response = requests.post(
        f"{settings.PAYPAL_API_URL}/v1/oauth2/token",
        auth=auth,
        data=data,
        headers=headers,
        timeout=10
    )
    return response.json()['access_token']


def initiate_mpesa_payment(amount, phone_number, order_id):
    """Initiate M-Pesa STK push payment with enhanced error handling and retry logic"""
    try:
        # Validate amount first (can be Decimal or float)
        try:
            if hasattr(amount, 'quantize'):
                amount_float = float(amount)
            else:
                amount_float = float(amount)

            if amount_float <= 0:
                return {'errorMessage': 'Invalid amount. Amount must be greater than 0.'}
            amount_int = int(amount_float)
        except (ValueError, TypeError):
            return {'errorMessage': 'Invalid amount format'}

        # Get access token with retry logic
        max_retries = 3
        access_token = None

        for attempt in range(max_retries):
            try:
                auth_url = "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
                auth_response = requests.get(
                    auth_url,
                    auth=(settings.MPESA_CONSUMER_KEY, settings.MPESA_CONSUMER_SECRET),
                    timeout=10,
                    headers={
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                        'Cache-Control': 'no-cache, no-store, must-revalidate',
                        'Pragma': 'no-cache',
                    }
                )

                # Check for Incapsula block
                if auth_response.status_code == 403 and 'Incapsula' in auth_response.text:
                    logger.warning(f"Incapsula block detected during auth, attempt {attempt + 1}")
                    if attempt < max_retries - 1:
                        time.sleep(5)  # Longer delay
                        continue
                    else:
                        return {'errorMessage': 'Service temporarily unavailable. Please try again in a few minutes.'}

                auth_response.raise_for_status()
                access_token = auth_response.json().get('access_token')
                break  # Success, break out of retry loop

            except requests.exceptions.RequestException as e:
                logger.error(f"M-Pesa auth error (attempt {attempt + 1}): {str(e)}")
                if attempt == max_retries - 1:  # Last attempt
                    return {'errorMessage': 'M-Pesa service temporarily unavailable'}
                time.sleep(3)  # Wait before retry
                continue

        if not access_token:
            return {'errorMessage': 'Failed to get access token'}

        # Format phone number
        if phone_number.startswith('0'):
            phone_number = '254' + phone_number[1:]
        elif not phone_number.startswith('254'):
            phone_number = '254' + phone_number

        # Prepare STK push request
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        password_str = f"{settings.MPESA_SHORTCODE}{settings.MPESA_PASSKEY}{timestamp}"
        password = base64.b64encode(password_str.encode("utf-8")).decode("utf-8")
        payload = {
            "BusinessShortCode": settings.MPESA_SHORTCODE,
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": amount_int,
            "PartyA": phone_number,
            "PartyB": settings.MPESA_SHORTCODE,
            "PhoneNumber": phone_number,
            "CallBackURL": settings.MPESA_CALLBACK_URL or "https://1a0b711fbccf.ngrok-free.app/payment/webhook/mpesa/",
            "AccountReference": f"ORDER_{order_id}",
            "TransactionDesc": "ASAI Payment"
        }

        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Cache-Control': 'no-cache, no-store, must-revalidate',
            'Pragma': 'no-cache',
        }

        logger.info(f"[M-Pesa] Initiating payment: {amount_int} KES to {phone_number} for order {order_id}")

        # Make payment request with retry logic
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    "https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest",
                    json=payload,
                    headers=headers,
                    timeout=15
                )

                # Check if we got an Incapsula block page
                if response.status_code == 403 and 'Incapsula' in response.text:
                    logger.warning(f"Incapsula block detected, attempt {attempt + 1}")
                    if attempt < max_retries - 1:
                        time.sleep(5)  # Longer delay for Incapsula
                        continue
                    else:
                        return {
                            'errorMessage': 'Payment service temporarily blocked. Please try again in a few minutes.'
                        }

                # Check for other error statuses
                if response.status_code >= 400:
                    logger.error(f"M-Pesa API returned status {response.status_code}")
                    if attempt < max_retries - 1:
                        time.sleep(3)
                        continue
                    else:
                        try:
                            error_data = response.json()
                            return {'errorMessage': error_data.get('errorMessage', 'M-Pesa service error')}
                        except:
                            return {'errorMessage': f'M-Pesa API error: {response.status_code}'}

                response.raise_for_status()
                result = response.json()

                # Check if it's a successful response
                if 'ResponseCode' in result and result.get('ResponseCode') == '0':
                    logger.info(f"M-Pesa payment initiated successfully: {result.get('CheckoutRequestID')}")
                    return result
                else:
                    error_msg = result.get('errorMessage') or result.get(
                        'ResponseDescription') or 'M-Pesa payment failed'
                    logger.error(f"M-Pesa payment failed: {error_msg}")
                    return {'errorMessage': error_msg}

            except requests.exceptions.RequestException as e:
                logger.error(f"M-Pesa API error (attempt {attempt + 1}): {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(3)
                    continue
                else:
                    return {'errorMessage': 'M-Pesa service temporarily unavailable. Please try again.'}

    except Exception as e:
        logger.error(f"M-Pesa initiation error: {str(e)}")
        return {'errorMessage': 'Failed to initiate M-Pesa payment'}



def is_currency_supported(currency, provider):
    """Check if a currency is supported by a payment provider"""
    if provider == 'PAYPAL':
        return is_paypal_currency_supported(currency)
    elif provider == 'MPESA':
        # M-Pesa now supports all currencies via conversion to KES
        return True
    return False


def get_prioritized_payment_methods(request):
    country = getattr(request, 'country', None)

    if country == 'KE':  # Kenya
        return ['mpesa', 'paypal']
    else:  # All other countries
        return ['paypal', 'mpesa']