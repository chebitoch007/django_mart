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
    return {
        'DEFAULT_CURRENCY': settings.DEFAULT_CURRENCY,
        'CURRENCIES': settings.CURRENCIES
    }