# payment/paystack_utils.py

import requests
import logging
from django.conf import settings
from django.core.cache import cache
from decimal import Decimal, ROUND_HALF_UP
from djmoney.money import Money

logger = logging.getLogger(__name__)


class PaystackClient:
    """Paystack API client with connection pooling and retry logic"""

    def __init__(self):
        self.secret_key = settings.PAYSTACK_SECRET_KEY
        self.public_key = settings.PAYSTACK_PUBLIC_KEY
        self.api_url = "https://api.paystack.co"
        self.timeout = 30
        self.max_retries = 3
        self.retry_delay = 1

    def _get_headers(self):
        """Get request headers with authorization"""
        return {
            'Authorization': f'Bearer {self.secret_key}',
            'Content-Type': 'application/json',
        }

    def _make_request(self, method, endpoint, data=None, retry_count=0):
        """Make API request with retry logic"""
        try:
            url = f"{self.api_url}{endpoint}"
            headers = self._get_headers()

            response = requests.request(
                method,
                url,
                json=data,
                headers=headers,
                timeout=self.timeout
            )

            response.raise_for_status()
            return response.json()

        except requests.exceptions.Timeout:
            if retry_count < self.max_retries:
                import time
                time.sleep(self.retry_delay * (2 ** retry_count))
                return self._make_request(method, endpoint, data, retry_count + 1)
            raise Exception("Paystack API timeout - please try again")

        except requests.exceptions.RequestException as e:
            logger.error(f"Paystack API error: {str(e)}")
            if hasattr(e.response, 'json'):
                try:
                    error_data = e.response.json()
                    raise Exception(error_data.get('message', 'Payment service error'))
                except:
                    pass
            raise Exception("Payment service temporarily unavailable")


paystack_client = PaystackClient()


def initialize_paystack_transaction(amount, email, order_id, metadata=None):
    """
    Initialize a Paystack transaction

    Args:
        amount: Money object or numeric value (will be converted to kobo/cents)
        email: Customer email
        order_id: Order ID for reference
        metadata: Additional metadata dict

    Returns:
        dict: Transaction data with authorization_url and reference
    """
    try:
        # Normalize amount
        if isinstance(amount, Money):
            currency = amount.currency.code
            amount_value = amount.amount
        else:
            amount_value = Decimal(str(amount))
            currency = settings.DEFAULT_CURRENCY

        # Validate currency
        if not is_paystack_currency_supported(currency):
            logger.warning(f"Unsupported currency {currency}, defaulting to NGN")
            currency = 'NGN'

        # Convert to smallest currency unit (kobo for NGN, cents for others)
        amount_in_minor = int(amount_value * 100)

        # Build callback URL
        from django.urls import reverse
        callback_url = f"{settings.BASE_URL}{reverse('payment:paystack_callback')}"

        # Prepare transaction data
        payload = {
            "email": email,
            "amount": amount_in_minor,
            "currency": currency,
            "reference": f"ORDER_{order_id}_{generate_reference()}",
            "callback_url": callback_url,
            "metadata": {
                "order_id": order_id,
                "custom_fields": [
                    {
                        "display_name": "Order ID",
                        "variable_name": "order_id",
                        "value": order_id
                    }
                ],
                **(metadata or {})
            }
        }

        result = paystack_client._make_request('POST', '/transaction/initialize', payload)

        if result.get('status'):
            logger.info(f"Paystack transaction initialized: {result['data']['reference']}")
            return {
                'success': True,
                'authorization_url': result['data']['authorization_url'],
                'access_code': result['data']['access_code'],
                'reference': result['data']['reference']
            }
        else:
            logger.error(f"Paystack initialization failed: {result.get('message')}")
            return {
                'success': False,
                'error': result.get('message', 'Failed to initialize transaction')
            }

    except Exception as e:
        logger.exception(f"Paystack initialization error: {e}")
        return {
            'success': False,
            'error': str(e)
        }


def verify_paystack_transaction(reference):
    """
    Verify a Paystack transaction

    Args:
        reference: Transaction reference

    Returns:
        dict: Verification result with status and data
    """
    try:
        result = paystack_client._make_request('GET', f'/transaction/verify/{reference}')

        if result.get('status'):
            data = result['data']
            logger.info(f"Paystack transaction verified: {reference} - {data['status']}")
            return {
                'success': True,
                'status': data['status'],
                'amount': data['amount'] / 100,  # Convert from kobo/cents
                'currency': data['currency'],
                'reference': data['reference'],
                'paid_at': data.get('paid_at'),
                'channel': data.get('channel'),
                'customer': data.get('customer'),
                'metadata': data.get('metadata', {})
            }
        else:
            return {
                'success': False,
                'error': result.get('message', 'Verification failed')
            }

    except Exception as e:
        logger.error(f"Paystack verification error: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }


def is_paystack_currency_supported(currency):
    """Check if currency is supported by Paystack"""
    supported = {
        'NGN',  # Nigerian Naira
        'GHS',  # Ghanaian Cedi
        'ZAR',  # South African Rand
        'USD',  # US Dollar
        'KES',  # Kenyan Shilling
    }
    return currency.upper() in supported


def generate_reference():
    """Generate a unique reference suffix"""
    import uuid
    return str(uuid.uuid4())[:8].upper()


def get_paystack_banks():
    """Get list of Nigerian banks for bank transfers"""
    try:
        cache_key = 'paystack_banks'
        banks = cache.get(cache_key)

        if banks:
            return banks

        result = paystack_client._make_request('GET', '/bank')

        if result.get('status'):
            banks = result['data']
            cache.set(cache_key, banks, 60 * 60 * 24)  # Cache for 24 hours
            return banks

        return []

    except Exception as e:
        logger.error(f"Error fetching Paystack banks: {str(e)}")
        return []


def create_paystack_refund(transaction_id, amount=None):
    """
    Create a refund for a Paystack transaction

    Args:
        transaction_id: Transaction ID or reference
        amount: Amount to refund (in kobo/cents). If None, full refund

    Returns:
        dict: Refund result
    """
    try:
        payload = {'transaction': transaction_id}
        if amount:
            payload['amount'] = int(amount * 100)

        result = paystack_client._make_request('POST', '/refund', payload)

        if result.get('status'):
            logger.info(f"Paystack refund created for {transaction_id}")
            return {
                'success': True,
                'data': result['data']
            }
        else:
            return {
                'success': False,
                'error': result.get('message', 'Refund failed')
            }

    except Exception as e:
        logger.error(f"Paystack refund error: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }