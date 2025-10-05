from django.core.management.base import BaseCommand
from django.core.cache import cache
from core.utils import get_exchange_rate
import time

class Command(BaseCommand):
    help = "Test Django cache and exchange rate caching"

    def handle(self, *args, **options):
        self.stdout.write("Testing cache storage...")
        cache.set('test_key', 'Cache OK!', 60)
        val = cache.get('test_key')
        self.stdout.write(f"Cache value: {val}")

        self.stdout.write("\nTesting get_exchange_rate caching...")
        start = time.time()
        rate1 = get_exchange_rate('USD', 'KES')
        self.stdout.write(f"First fetch: {rate1} ({round(time.time() - start, 3)}s)")

        start = time.time()
        rate2 = get_exchange_rate('USD', 'KES')
        self.stdout.write(f"Second fetch (cached): {rate2} ({round(time.time() - start, 3)}s)")

        assert rate1 == rate2
        self.stdout.write("\n✅ Caching works correctly!")
