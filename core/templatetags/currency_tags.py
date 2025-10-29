# core/templatetags/currency_tags.py
from django import template
from django.conf import settings

register = template.Library()

@register.inclusion_tag("core/currency_selector.html", takes_context=True)
def currency_selector(context):
    """
    Render a currency selector dropdown populated from settings.CURRENCIES.
    """
    request = context.get("request")
    selected = request.session.get("currency", settings.DEFAULT_CURRENCY)

    # Build dropdown options from CURRENCIES (tuple of codes)
    currencies = [
        {
            "code": code,
            "name": getattr(settings, "CURRENCY_NAMES", {}).get(code, code),
            "symbol": getattr(settings, "CURRENCY_SYMBOLS", {}).get(code, code),
            "selected": code == selected,
        }
        for code in settings.CURRENCIES
    ]

    return {"currencies": currencies, "selected_currency": selected}
