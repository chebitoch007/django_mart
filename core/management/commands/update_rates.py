# core/management/commands/update_rates.py
from django.core.management.base import BaseCommand
from core.utils import get_exchange_rate
from django.conf import settings


class Command(BaseCommand):
    help = 'Updates currency exchange rates'

    def handle(self, *args, **options):
        base_currency = settings.DEFAULT_CURRENCY
        currencies = [c[0] for c in settings.CURRENCIES if c[0] != base_currency]

        for currency in currencies:
            rate = get_exchange_rate(base_currency, currency)
            convert_currency()
            self.stdout.write(f'Updated {base_currency}/{currency}: {rate}')