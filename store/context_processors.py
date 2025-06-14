from django.conf import settings
from .models import Category

def categories(request):
    return {
        'categories': Category.objects.all()
    }

def currency_context(request):
    return {
        'DEFAULT_CURRENCY': settings.DEFAULT_CURRENCY,
        'CURRENCIES': settings.CURRENCIES
    }