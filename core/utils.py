# core/utils.py
from decimal import Decimal, ROUND_HALF_UP
import logging
from django.core.cache import cache
from django.conf import settings
import requests

logger = logging.getLogger(__name__)

SUPPORTED_BY_FRANKFURTER = {
    "USD", "EUR", "GBP", "CHF", "CAD", "AUD", "NZD",
    "SEK", "NOK", "DKK", "JPY", "CNY"
}


def get_exchange_rate(base_currency, target_currency):
    """Fetch exchange rate with automatic fallback to backup APIs and local rates."""

    if base_currency == target_currency:
        return Decimal('1.0')

    cache_key = f"rate_{base_currency}_{target_currency}"
    cached_rate = cache.get(cache_key)
    if cached_rate is not None:
        try:
            return Decimal(str(cached_rate))
        except (TypeError, ValueError):
            logger.warning(f"Invalid cached rate value: {cached_rate}")

    e1 = None
    e2 = None

    # === 1️⃣ Try Exchangerate.host ===
    try:
        base_url = "https://api.exchangerate.host/latest"
        params = {"base": base_currency, "symbols": target_currency}

        api_key = getattr(settings, "EXCHANGERATE_API_KEY", "")
        if api_key:
            params["access_key"] = api_key

        logger.debug(f"Fetching exchange rate from exchangerate.host: {base_currency}->{target_currency}")
        response = requests.get(base_url, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()

        if data.get("success", True) and "rates" in data:
            rate = data["rates"].get(target_currency)
            if rate:
                decimal_rate = Decimal(str(rate)).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
                cache.set(cache_key, float(decimal_rate), 14400)
                return decimal_rate
            else:
                raise ValueError(f"Currency {target_currency} not found in exchangerate.host response")

        raise ValueError(data.get("error", {}).get("info", "Unknown exchangerate.host error"))

    except Exception as ex1:
        e1 = ex1
        logger.warning(f"Primary API failed: {e1}")

    # === 2️⃣ Try Frankfurter.app if supported ===
    if base_currency in SUPPORTED_BY_FRANKFURTER and target_currency in SUPPORTED_BY_FRANKFURTER:
        try:
            fallback_url = "https://api.frankfurter.app/latest"
            params = {"from": base_currency, "to": target_currency}
            logger.debug(f"Fetching exchange rate from frankfurter.app: {base_currency}->{target_currency}")
            response = requests.get(fallback_url, params=params, timeout=5)
            response.raise_for_status()
            data = response.json()

            if "rates" in data and target_currency in data["rates"]:
                rate = data["rates"][target_currency]
                decimal_rate = Decimal(str(rate)).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
                cache.set(cache_key, float(decimal_rate), 14400)
                return decimal_rate
            else:
                raise ValueError("Frankfurter API did not return valid data")

        except Exception as ex2:
            e2 = ex2
            logger.warning(f"Backup API failed: {ex2}")
    else:
        logger.info(f"Skipping Frankfurter fallback for {base_currency}->{target_currency} (unsupported currency).")

    # === 3️⃣ Final fallback ===
    logger.error(f"Both APIs failed for {base_currency}->{target_currency}. Using local fallback.")
    return get_fallback_rate(base_currency, target_currency, str(e2 or e1 or 'Unknown error'))


def get_fallback_rate(base_currency, target_currency, error_info=None):
    """Enhanced fallback rates with better routing and precision."""
    logger.warning("Using fallback exchange rates")

    fallback_rates = {
        'USD': {
            'EUR': Decimal('0.93'),
            'GBP': Decimal('0.79'),
            'KES': Decimal('129.20'),  # updated from 130.50
            'UGX': Decimal('3700'),
            'TZS': Decimal('2500'),
        },
        'EUR': {
            'USD': Decimal('1.07'),
            'GBP': Decimal('0.85'),
            'KES': Decimal('140.00'),
            'UGX': Decimal('4200'),
            'TZS': Decimal('2700'),
        },
        'GBP': {
            'USD': Decimal('1.27'),
            'EUR': Decimal('1.18'),
            'KES': Decimal('174.50'),  # updated from 165.00
            'UGX': Decimal('4700'),
            'TZS': Decimal('3500'),  # updated from 3000
        },
        'KES': {
            'USD': Decimal('0.0077'),
            'EUR': Decimal('0.0071'),
            'GBP': Decimal('0.00573'),  # inverse of ~174.5
            'UGX': Decimal('27.30'),  # updated from 28.50
            'TZS': Decimal('19.20'),
        },
        'UGX': {
            'USD': Decimal('0.00027'),
            'EUR': Decimal('0.00024'),
            'GBP': Decimal('0.00021'),
            'KES': Decimal('0.0367'),  # inverse of ~27.30
            'TZS': Decimal('0.67'),
        },
        'TZS': {
            'USD': Decimal('0.00040'),
            'EUR': Decimal('0.00037'),
            'GBP': Decimal('0.00029'),  # inverse of ~3500
            'KES': Decimal('0.052'),
            'UGX': Decimal('1.49'),
        },
    }

    if base_currency in fallback_rates and target_currency in fallback_rates[base_currency]:
        return fallback_rates[base_currency][target_currency]

    if base_currency in fallback_rates and 'USD' in fallback_rates[base_currency]:
        if 'USD' in fallback_rates and target_currency in fallback_rates['USD']:
            return fallback_rates[base_currency]['USD'] * fallback_rates['USD'][target_currency]

    for intermediate in ['EUR', 'GBP', 'KES']:
        if (base_currency in fallback_rates and intermediate in fallback_rates[base_currency] and
                intermediate in fallback_rates and target_currency in fallback_rates[intermediate]):
            return fallback_rates[base_currency][intermediate] * fallback_rates[intermediate][target_currency]

    logger.warning(f"No fallback rate available for {base_currency}->{target_currency}. Error: {error_info}. Using 1.0")
    return Decimal('1.0')
