from django.core.management.base import BaseCommand
from core.utils import get_exchange_rate

class Command(BaseCommand):
    help = "Test exchange rate fetching"

    def handle(self, *args, **options):
        pairs = [('USD', 'KES'), ('EUR', 'USD'), ('KES', 'UGX')]
        for base, target in pairs:
            rate = get_exchange_rate(base, target)
            self.stdout.write(f"{base} -> {target}: {rate}")
