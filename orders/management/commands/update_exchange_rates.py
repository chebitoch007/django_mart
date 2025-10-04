from django.core.management.base import BaseCommand
from django.core.cache import cache
from django.conf import settings
from orders.views import get_exchange_rate
from orders.models import CurrencyRate
import requests


class Command(BaseCommand):
    help = 'Updates exchange rates in cache and database'



    def handle(self, *args, **options):
        base_currency = settings.DEFAULT_CURRENCY
        currencies = [code for code, _ in settings.CURRENCIES if code != base_currency]


        for currency in currencies:
            rate = get_exchange_rate(base_currency, currency)

            if rate == 1.0 and base_currency != currency:
                # Send alert about failed update
                from django.core.mail import mail_admins
                mail_admins(
                    'Exchange Rate Update Failed',
                    f'Failed to update {base_currency} to {currency} rate'
                )

            # Update database
            CurrencyRate.objects.update_or_create(
                base_currency=base_currency,
                target_currency=currency,
                defaults={'rate': rate}
            )

            self.stdout.write(f'Updated {base_currency} to {currency}: {rate}')