# store/templatetags/currency_tags.py
from django import template
from django.conf import settings
from decimal import Decimal
from core.utils import get_exchange_rate
from djmoney.money import Money
import logging

register = template.Library()
logger = logging.getLogger(__name__)


@register.filter
def get_item(dictionary, key):
    """Get item from dictionary by key"""
    if dictionary is None:
        return None
    return dictionary.get(key, '')


@register.filter
def convert_currency(price, target_currency):
    """
    Convert a Money object to target currency.
    This filter ensures prices are converted on every page load.
    """
    if not price or not target_currency:
        return price

    # If price is already in target currency, return as-is
    if hasattr(price, 'currency') and str(price.currency) == target_currency:
        return price

    try:
        # Get the base currency
        base_currency = str(price.currency) if hasattr(price, 'currency') else settings.DEFAULT_CURRENCY

        # Get the amount
        amount = price.amount if hasattr(price, 'amount') else Decimal(str(price))

        # Convert if currencies are different
        if base_currency != target_currency:
            rate = get_exchange_rate(base_currency, target_currency)
            converted_amount = amount * rate
            return Money(converted_amount, target_currency)

        return price

    except Exception as e:
        logger.error(f"Currency conversion error: {e}")
        return price


@register.simple_tag(takes_context=True)
def get_user_currency(context):
    """Get the user's selected currency from session"""
    request = context.get('request')
    if request and hasattr(request, 'session'):
        return request.session.get('user_currency', settings.DEFAULT_CURRENCY)
    return settings.DEFAULT_CURRENCY


@register.simple_tag(takes_context=True)
def display_price(context, price):
    """
    Display a price in the user's selected currency with proper formatting.
    Usage: {% display_price product.price %}
    """
    if not price:
        return ""

    # Get user's selected currency
    request = context.get('request')
    user_currency = settings.DEFAULT_CURRENCY
    if request and hasattr(request, 'session'):
        user_currency = request.session.get('user_currency', settings.DEFAULT_CURRENCY)

    try:
        # Convert to user's currency if needed
        if hasattr(price, 'currency') and str(price.currency) != user_currency:
            base_currency = str(price.currency)
            amount = price.amount
            rate = get_exchange_rate(base_currency, user_currency)
            converted_amount = amount * rate
            price = Money(converted_amount, user_currency)

        # Get amount and currency
        amount = price.amount if hasattr(price, 'amount') else Decimal(str(price))
        currency = str(price.currency) if hasattr(price, 'currency') else user_currency

        # Get format configuration
        format_config = settings.CURRENCY_FORMATS.get(currency, {})
        decimal_places = format_config.get('decimal_places', 2)
        symbol = settings.CURRENCY_SYMBOLS.get(currency, currency)

        # Format the amount
        formatted_amount = f"{amount:,.{decimal_places}f}"

        return f"{symbol} {formatted_amount}"

    except Exception as e:
        logger.error(f"Price display error: {e}")
        return str(price)


@register.filter
def format_price(price, currency=None):
    """
    Format price with currency symbol.
    Usage: {{ product.price|format_price }}
    """
    if not price:
        return ""

    try:
        amount = price.amount if hasattr(price, 'amount') else Decimal(str(price))
        curr = currency or (str(price.currency) if hasattr(price, 'currency') else settings.DEFAULT_CURRENCY)

        format_config = settings.CURRENCY_FORMATS.get(curr, {})
        decimal_places = format_config.get('decimal_places', 2)
        symbol = settings.CURRENCY_SYMBOLS.get(curr, curr)
        formatted_amount = f"{amount:,.{decimal_places}f}"

        return f"{symbol} {formatted_amount}"
    except Exception as e:
        logger.error(f"Price formatting error: {e}")
        return str(price)


@register.simple_tag(takes_context=True)
def convert_and_display(context, price):
    """
    Convert price to user's currency and display with proper formatting.
    This is the recommended tag for displaying prices in templates.
    Usage: {% convert_and_display product.price %}
    """
    if not price:
        return ""

    # Get user's selected currency
    request = context.get('request')
    user_currency = settings.DEFAULT_CURRENCY
    if request and hasattr(request, 'session'):
        user_currency = request.session.get('user_currency', settings.DEFAULT_CURRENCY)

    try:
        # Get base values
        base_currency = str(price.currency) if hasattr(price, 'currency') else settings.DEFAULT_CURRENCY
        amount = price.amount if hasattr(price, 'amount') else Decimal(str(price))

        # Convert if needed
        if base_currency != user_currency:
            rate = get_exchange_rate(base_currency, user_currency)
            amount = amount * rate

        # Format
        format_config = settings.CURRENCY_FORMATS.get(user_currency, {})
        decimal_places = format_config.get('decimal_places', 2)
        symbol = settings.CURRENCY_SYMBOLS.get(user_currency, user_currency)
        formatted_amount = f"{amount:,.{decimal_places}f}"

        return f"{symbol} {formatted_amount}"

    except Exception as e:
        logger.error(f"Convert and display error: {e}")
        return str(price)



