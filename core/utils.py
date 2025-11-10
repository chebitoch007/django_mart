# core/utils.py - Improved exchange rate handling

import logging
from decimal import Decimal
from django.core.cache import cache
from django.conf import settings

logger = logging.getLogger(__name__)

# Fallback exchange rates (updated regularly)
FALLBACK_RATES = {
    # Base: 1 KES
    'KES': {
        'USD': Decimal('0.0077'),  # 1 KES = 0.0077 USD
        'EUR': Decimal('0.0071'),  # 1 KES = 0.0071 EUR
        'GBP': Decimal('0.0061'),  # 1 KES = 0.0061 GBP
        'KES': Decimal('1.0'),  # 1 KES = 1 KES
        'UGX': Decimal('28.57'),  # 1 KES = 28.57 UGX
        'TZS': Decimal('20.41'),  # 1 KES = 20.41 TZS
    },
    # Base: 1 USD
    'USD': {
        'KES': Decimal('129.87'),  # 1 USD = 129.87 KES
        'EUR': Decimal('0.92'),  # 1 USD = 0.92 EUR
        'GBP': Decimal('0.79'),  # 1 USD = 0.79 GBP
        'USD': Decimal('1.0'),  # 1 USD = 1 USD
        'UGX': Decimal('3710.0'),  # 1 USD = 3710 UGX
        'TZS': Decimal('2650.0'),  # 1 USD = 2650 TZS
    },
    # Base: 1 EUR
    'EUR': {
        'KES': Decimal('140.85'),  # 1 EUR = 140.85 KES
        'USD': Decimal('1.09'),  # 1 EUR = 1.09 USD
        'GBP': Decimal('0.86'),  # 1 EUR = 0.86 GBP
        'EUR': Decimal('1.0'),  # 1 EUR = 1 EUR
        'UGX': Decimal('4024.0'),  # 1 EUR = 4024 UGX
        'TZS': Decimal('2875.0'),  # 1 EUR = 2875 TZS
    },
    # Base: 1 GBP
    'GBP': {
        'KES': Decimal('163.93'),  # 1 GBP = 163.93 KES
        'USD': Decimal('1.27'),  # 1 GBP = 1.27 USD
        'EUR': Decimal('1.16'),  # 1 GBP = 1.16 EUR
        'GBP': Decimal('1.0'),  # 1 GBP = 1 GBP
        'UGX': Decimal('4680.0'),  # 1 GBP = 4680 UGX
        'TZS': Decimal('3345.0'),  # 1 GBP = 3345 TZS
    },
    # Base: 1 UGX
    'UGX': {
        'KES': Decimal('0.035'),  # 1 UGX = 0.035 KES
        'USD': Decimal('0.00027'),  # 1 UGX = 0.00027 USD
        'EUR': Decimal('0.00025'),  # 1 UGX = 0.00025 EUR
        'GBP': Decimal('0.00021'),  # 1 UGX = 0.00021 GBP
        'UGX': Decimal('1.0'),  # 1 UGX = 1 UGX
        'TZS': Decimal('0.714'),  # 1 UGX = 0.714 TZS
    },
    # Base: 1 TZS
    'TZS': {
        'KES': Decimal('0.049'),  # 1 TZS = 0.049 KES
        'USD': Decimal('0.00038'),  # 1 TZS = 0.00038 USD
        'EUR': Decimal('0.00035'),  # 1 TZS = 0.00035 EUR
        'GBP': Decimal('0.00030'),  # 1 TZS = 0.00030 GBP
        'UGX': Decimal('1.40'),  # 1 TZS = 1.40 UGX
        'TZS': Decimal('1.0'),  # 1 TZS = 1 TZS
    },
}


def get_exchange_rate(from_currency, to_currency):
    """
    Get exchange rate from one currency to another.
    Uses API with fallback to static rates.

    Args:
        from_currency (str): Source currency code (e.g., 'USD')
        to_currency (str): Target currency code (e.g., 'KES')

    Returns:
        Decimal: Exchange rate
    """
    # Same currency, no conversion needed
    if from_currency == to_currency:
        return Decimal('1.0')

    # Validate currencies
    if from_currency not in settings.CURRENCIES or to_currency not in settings.CURRENCIES:
        logger.warning(f"Invalid currency pair: {from_currency} -> {to_currency}")
        return Decimal('1.0')

    # Try cache first
    cache_key = f'exchange_rate_{from_currency}_{to_currency}'
    cached_rate = cache.get(cache_key)

    if cached_rate is not None:
        return Decimal(str(cached_rate))

    # Try API (you can implement this later)
    # rate = try_api_exchange_rate(from_currency, to_currency)
    # if rate:
    #     cache.set(cache_key, str(rate), settings.CURRENCY_CACHE_TIMEOUT)
    #     return rate

    # Use fallback rates
    try:
        if from_currency in FALLBACK_RATES and to_currency in FALLBACK_RATES[from_currency]:
            rate = FALLBACK_RATES[from_currency][to_currency]
            # Cache fallback rate for 1 hour
            cache.set(cache_key, str(rate), 3600)
            return rate
        else:
            logger.warning(f"No fallback rate for {from_currency} -> {to_currency}")
            return Decimal('1.0')
    except Exception as e:
        logger.error(f"Error getting exchange rate: {e}")
        return Decimal('1.0')


def convert_money(amount, from_currency, to_currency):
    """
    Convert an amount from one currency to another.

    Args:
        amount: Amount to convert (Decimal, float, or string)
        from_currency (str): Source currency code
        to_currency (str): Target currency code

    Returns:
        Decimal: Converted amount
    """
    if from_currency == to_currency:
        return Decimal(str(amount))

    rate = get_exchange_rate(from_currency, to_currency)
    converted = Decimal(str(amount)) * rate

    # Round to appropriate decimal places
    format_config = settings.CURRENCY_FORMATS.get(to_currency, {})
    decimal_places = format_config.get('decimal_places', 2)

    return converted.quantize(Decimal('0.1') ** decimal_places)