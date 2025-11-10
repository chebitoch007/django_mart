from django.conf import settings
from .models import Category

def top_level_categories(request):
    return {
        'top_level_categories': Category.objects.filter(
            parent=None,
            is_active=True
        )
    }


def currency_context(request):
    """
    Add currency information to all templates.
    """
    user_currency = request.session.get('user_currency', settings.DEFAULT_CURRENCY)

    return {
        'DEFAULT_CURRENCY': settings.DEFAULT_CURRENCY,
        'CURRENCIES': settings.CURRENCIES,
        'CURRENCY_NAMES': settings.CURRENCY_NAMES,
        'CURRENCY_SYMBOLS': settings.CURRENCY_SYMBOLS,
        'user_currency': user_currency,
    }