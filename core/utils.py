# core/utils.py
from decimal import Decimal, ROUND_HALF_UP
import logging
from django.core.cache import cache
from django.conf import settings
import requests

logger = logging.getLogger(__name__)


def get_exchange_rate(base_currency, target_currency):
    """Fetch exchange rate with improved error handling, fallbacks, and decimal precision"""
    # If same currency, return 1.0 immediately
    if base_currency == target_currency:
        return Decimal('1.0')

    cache_key = f'rate_{base_currency}_{target_currency}'
    cached_rate = cache.get(cache_key)

    if cached_rate is not None:
        try:
            return Decimal(str(cached_rate))
        except (TypeError, ValueError):
            logger.warning(f"Invalid cached rate value: {cached_rate}")

    try:
        # Build API URL
        base_url = "https://api.exchangerate.host/latest"
        params = {
            'base': base_currency,
            'symbols': target_currency,
        }

        # Only use API key in production
        if not settings.DEBUG:
            api_key = settings.EXCHANGERATE_API_KEY
            if api_key:
                params['access_key'] = api_key

        logger.debug(f"Fetching exchange rate: {base_currency}->{target_currency}")
        response = requests.get(base_url, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()

        if data.get('success', False):
            rate = data['rates'].get(target_currency)
            if rate is None:
                logger.warning(f"Target currency {target_currency} not in API response")
                raise ValueError(f"Currency {target_currency} not found")

            # Convert to Decimal with proper rounding
            decimal_rate = Decimal(str(rate)).quantize(
                Decimal('0.000001'),
                rounding=ROUND_HALF_UP
            )
            cache.set(cache_key, float(decimal_rate), 14400)  # Cache for 4 hours
            return decimal_rate
        else:
            error_info = data.get('error', {}).get('info', 'Unknown API error')
            logger.error(f"Exchange rate API error: {error_info}")
            raise ValueError(f"API error: {error_info}")

    except Exception as e:
        logger.error(f"Error fetching exchange rate: {str(e)}")
        # Use fallback rates with detailed error info
        return get_fallback_rate(base_currency, target_currency, str(e))


def get_fallback_rate(base_currency, target_currency, error_info=None):
    """Enhanced fallback rates with better routing and decimal precision"""
    logger.warning("Using fallback exchange rates")

    # Define fallback rates as Decimals
    fallback_rates = {
        'USD': {
            'EUR': Decimal('0.93'),
            'GBP': Decimal('0.79'),
            'KES': Decimal('130.50'),
            'UGX': Decimal('3700'),
            'TZS': Decimal('2500')
        },
        'EUR': {
            'USD': Decimal('1.07'),
            'GBP': Decimal('0.85'),
            'KES': Decimal('140.00'),
            'UGX': Decimal('4200'),
            'TZS': Decimal('2700')
        },
        'GBP': {
            'USD': Decimal('1.27'),
            'EUR': Decimal('1.18'),
            'KES': Decimal('165.00'),
            'UGX': Decimal('4700'),
            'TZS': Decimal('3000')
        },
        'KES': {
            'USD': Decimal('0.0077'),
            'EUR': Decimal('0.0071'),
            'GBP': Decimal('0.0061'),
            'UGX': Decimal('28.50'),
            'TZS': Decimal('19.20')
        },
        'UGX': {
            'USD': Decimal('0.00027'),
            'EUR': Decimal('0.00024'),
            'GBP': Decimal('0.00021'),
            'KES': Decimal('0.035'),
            'TZS': Decimal('0.67')
        },
        'TZS': {
            'USD': Decimal('0.00040'),
            'EUR': Decimal('0.00037'),
            'GBP': Decimal('0.00033'),
            'KES': Decimal('0.052'),
            'UGX': Decimal('1.49')
        },
    }

    # Create a list of all known currencies
    all_currencies = set(fallback_rates.keys())
    for rates in fallback_rates.values():
        all_currencies.update(rates.keys())
    all_currencies = sorted(all_currencies)

    # 1. Try direct rate first
    if base_currency in fallback_rates and target_currency in fallback_rates[base_currency]:
        return fallback_rates[base_currency][target_currency]

    # 2. Try conversion through USD (most common)
    if base_currency in fallback_rates and 'USD' in fallback_rates[base_currency]:
        if 'USD' in fallback_rates and target_currency in fallback_rates['USD']:
            return fallback_rates[base_currency]['USD'] * fallback_rates['USD'][target_currency]

    # 3. Try other intermediate currencies
    for intermediate in ['EUR', 'GBP', 'KES']:
        if (base_currency in fallback_rates and intermediate in fallback_rates[base_currency] and
                intermediate in fallback_rates and target_currency in fallback_rates[intermediate]):
            return fallback_rates[base_currency][intermediate] * fallback_rates[intermediate][target_currency]

    # 4. Try to find any conversion path
    for intermediate in all_currencies:
        if (base_currency in fallback_rates and intermediate in fallback_rates[base_currency] and
                intermediate in fallback_rates and target_currency in fallback_rates[intermediate]):
            return fallback_rates[base_currency][intermediate] * fallback_rates[intermediate][target_currency]

    # 5. Final fallback: Use USD conversion if possible
    try:
        if base_currency != 'USD' and target_currency != 'USD':
            base_to_usd = get_fallback_rate(base_currency, 'USD', error_info)
            usd_to_target = get_fallback_rate('USD', target_currency, error_info)
            return base_to_usd * usd_to_target
    except Exception:
        pass

    # Log detailed warning if we reach this point
    logger.warning(
        f"No fallback rate available for {base_currency}->{target_currency}. "
        f"Error: {error_info or 'Unknown'}. Using 1.0"
    )

    return Decimal('1.0')