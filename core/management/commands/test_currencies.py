# core/management/commands/test_currencies.py
from django.core.management.base import BaseCommand
from django.conf import settings
from currencies.models import Currency
from core.utils import get_exchange_rate, convert_currency, format_currency
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Test currency conversion system'

    def add_arguments(self, parser):
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed output',
        )

    def handle(self, *args, **options):
        verbose = options.get('verbose', False)

        self.stdout.write(self.style.SUCCESS('\n=== Currency System Test ===\n'))

        # Test 1: Check if currencies are set up
        self.stdout.write('1. Checking currency setup...')
        currencies = Currency.objects.all()

        if not currencies.exists():
            self.stdout.write(self.style.ERROR('   ✗ No currencies found in database'))
            self.stdout.write(self.style.WARNING('   Run: python manage.py setup_currencies'))
            return

        self.stdout.write(self.style.SUCCESS(f'   ✓ Found {currencies.count()} currencies'))

        if verbose:
            for curr in currencies:
                self.stdout.write(f'     - {curr.code}: {curr.name} ({curr.symbol}) - Factor: {curr.factor}')

        # Test 2: Check base currency
        self.stdout.write('\n2. Checking base currency...')
        base_currencies = Currency.objects.filter(is_base=True)

        if base_currencies.count() != 1:
            self.stdout.write(self.style.ERROR(f'   ✗ Expected 1 base currency, found {base_currencies.count()}'))
        else:
            base = base_currencies.first()
            self.stdout.write(self.style.SUCCESS(f'   ✓ Base currency: {base.code} ({base.name})'))

        # Test 3: Test exchange rate retrieval
        self.stdout.write('\n3. Testing exchange rate retrieval...')
        test_pairs = [
            ('USD', 'KES'),
            ('USD', 'EUR'),
            ('EUR', 'GBP'),
            ('KES', 'UGX'),
        ]

        for from_curr, to_curr in test_pairs:
            try:
                rate = get_exchange_rate(from_curr, to_curr)
                self.stdout.write(
                    self.style.SUCCESS(f'   ✓ {from_curr} → {to_curr}: {rate}')
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'   ✗ {from_curr} → {to_curr}: {str(e)}')
                )

        # Test 4: Test currency conversion
        self.stdout.write('\n4. Testing currency conversion...')
        test_amount = Decimal('100.00')

        for from_curr, to_curr in test_pairs:
            try:
                converted = convert_currency(test_amount, from_curr, to_curr)
                formatted = format_currency(converted, to_curr)
                self.stdout.write(
                    self.style.SUCCESS(
                        f'   ✓ {test_amount} {from_curr} = {formatted}'
                    )
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'   ✗ {from_curr} → {to_curr}: {str(e)}')
                )

        # Test 5: Test currency formatting
        self.stdout.write('\n5. Testing currency formatting...')
        test_amounts = [
            (Decimal('1234.56'), 'USD'),
            (Decimal('12345'), 'KES'),
            (Decimal('123456'), 'UGX'),
            (Decimal('99.99'), 'EUR'),
        ]

        for amount, curr in test_amounts:
            try:
                formatted = format_currency(amount, curr)
                self.stdout.write(
                    self.style.SUCCESS(f'   ✓ {amount} {curr} → {formatted}')
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'   ✗ {amount} {curr}: {str(e)}')
                )

        # Test 6: Test cache
        self.stdout.write('\n6. Testing cache...')
        from django.core.cache import cache

        cache_key = 'rate_USD_KES'
        cached_rate = cache.get(cache_key)

        if cached_rate:
            self.stdout.write(
                self.style.SUCCESS(f'   ✓ Cache working: {cache_key} = {cached_rate}')
            )
        else:
            self.stdout.write(
                self.style.WARNING('   ⚠ No cached rates found (expected on first run)')
            )

        # Test 7: Check settings
        self.stdout.write('\n7. Checking settings...')

        checks = [
            ('DEFAULT_CURRENCY', settings.DEFAULT_CURRENCY),
            ('CURRENCY_CACHE_TIMEOUT', settings.CURRENCY_CACHE_TIMEOUT),
            ('OPENEXCHANGERATES_APP_ID', bool(getattr(settings, 'OPENEXCHANGERATES_APP_ID', None))),
        ]

        for setting, value in checks:
            if value:
                self.stdout.write(self.style.SUCCESS(f'   ✓ {setting}: {value}'))
            else:
                self.stdout.write(self.style.WARNING(f'   ⚠ {setting}: Not set or False'))

        # Test 8: Performance test
        self.stdout.write('\n8. Performance test (1000 conversions)...')
        import time

        start_time = time.time()
        for _ in range(1000):
            convert_currency(Decimal('100'), 'USD', 'KES')
        end_time = time.time()

        duration = end_time - start_time
        per_conversion = (duration / 1000) * 1000  # milliseconds

        if duration < 1.0:
            self.stdout.write(
                self.style.SUCCESS(
                    f'   ✓ 1000 conversions in {duration:.3f}s ({per_conversion:.3f}ms per conversion)'
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    f'   ⚠ 1000 conversions in {duration:.3f}s (consider optimization)'
                )
            )

        # Summary
        self.stdout.write('\n' + '=' * 50)
        self.stdout.write(self.style.SUCCESS('✅ Currency system test completed!'))
        self.stdout.write('\nNext steps:')
        self.stdout.write('  1. Run: python manage.py update_currency_rates')
        self.stdout.write('  2. Visit /admin/currencies/currency/ to manage currencies')
        self.stdout.write('  3. Set up cron job for automatic rate updates')
        self.stdout.write('=' * 50 + '\n')