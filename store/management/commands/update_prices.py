# store/management/commands/update_prices.py

from django.core.management.base import BaseCommand, CommandError
from store.models import Product
from core.utils import get_exchange_rate
from moneyed import Money
from decimal import Decimal
import csv


class Command(BaseCommand):
    help = 'Bulk update product prices with currency conversion'

    def add_arguments(self, parser):
        # Add command arguments
        parser.add_argument(
            '--from-currency',
            type=str,
            default='USD',
            help='Source currency (default: USD)'
        )

        parser.add_argument(
            '--to-currency',
            type=str,
            default='KES',
            help='Target currency (default: KES)'
        )

        parser.add_argument(
            '--markup',
            type=float,
            default=0,
            help='Markup percentage (e.g., 20 for 20%)'
        )

        parser.add_argument(
            '--csv-file',
            type=str,
            help='CSV file with product IDs and prices (id,price,discount_price)'
        )

        parser.add_argument(
            '--category',
            type=str,
            help='Only update products in this category slug'
        )

        parser.add_argument(
            '--no-price-only',
            action='store_true',
            help='Only update products with no price set'
        )

        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without actually updating'
        )

    def handle(self, *args, **options):
        from_currency = options['from_currency']
        to_currency = options['to_currency']
        markup = options['markup']
        csv_file = options['csv_file']
        category_slug = options['category']
        no_price_only = options['no_price_only']
        dry_run = options['dry_run']

        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('🔄 BULK PRICE UPDATE TOOL'))
        self.stdout.write(self.style.SUCCESS('=' * 60))

        # Get exchange rate
        rate = get_exchange_rate(from_currency, to_currency)
        markup_multiplier = 1 + (markup / 100)

        self.stdout.write(f'\n📊 Configuration:')
        self.stdout.write(f'   From: {from_currency}')
        self.stdout.write(f'   To: {to_currency}')
        self.stdout.write(f'   Exchange Rate: {rate}')
        self.stdout.write(f'   Markup: {markup}%')

        if dry_run:
            self.stdout.write(self.style.WARNING('\n   ⚠️  DRY RUN MODE - No changes will be saved\n'))

        # CSV Mode
        if csv_file:
            self.stdout.write(f'\n📄 Reading prices from CSV: {csv_file}')
            updated = self.update_from_csv(csv_file, to_currency, dry_run)
            self.stdout.write(self.style.SUCCESS(f'\n✅ Updated {updated} products from CSV'))
            return

        # Query products
        products = Product.objects.all()

        if category_slug:
            products = products.filter(category__slug=category_slug)
            self.stdout.write(f'\n🏷️  Filtering by category: {category_slug}')

        if no_price_only:
            products = products.filter(price__amount=0)
            self.stdout.write(f'\n⚠️  Only updating products with no price')

        total = products.count()
        self.stdout.write(f'\n📦 Found {total} products to process')

        if total == 0:
            self.stdout.write(self.style.WARNING('No products to update'))
            return

        # Confirm
        if not dry_run:
            confirm = input(f'\n❓ Update {total} products? (yes/no): ')
            if confirm.lower() != 'yes':
                self.stdout.write(self.style.WARNING('Cancelled'))
                return

        # Update products
        updated_count = 0
        skipped_count = 0

        self.stdout.write(f'\n🔄 Processing...\n')

        for product in products:
            try:
                if hasattr(product.price, 'amount'):
                    original_amount = product.price.amount

                    if original_amount == 0 and not no_price_only:
                        skipped_count += 1
                        continue

                    # Convert price
                    converted = Decimal(str(original_amount)) * rate * Decimal(str(markup_multiplier))

                    if not dry_run:
                        product.price = Money(converted, to_currency)

                        # Convert discount if exists
                        if product.discount_price and hasattr(product.discount_price, 'amount'):
                            discount_amount = product.discount_price.amount
                            converted_discount = Decimal(str(discount_amount)) * rate * Decimal(str(markup_multiplier))
                            product.discount_price = Money(converted_discount, to_currency)

                        product.save()

                    self.stdout.write(
                        f'  ✓ {product.name[:50]}: '
                        f'{original_amount} {from_currency} → '
                        f'{converted:.2f} {to_currency}'
                    )
                    updated_count += 1

            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  ✗ Error updating {product.name}: {str(e)}'))
                skipped_count += 1

        # Summary
        self.stdout.write(self.style.SUCCESS(f'\n' + '=' * 60))
        self.stdout.write(self.style.SUCCESS(f'✅ COMPLETED'))
        self.stdout.write(self.style.SUCCESS(f'   Updated: {updated_count}'))
        if skipped_count > 0:
            self.stdout.write(self.style.WARNING(f'   Skipped: {skipped_count}'))
        self.stdout.write(self.style.SUCCESS('=' * 60 + '\n'))

    def update_from_csv(self, csv_file, target_currency, dry_run):
        """Update prices from CSV file"""
        updated = 0

        try:
            with open(csv_file, 'r') as f:
                reader = csv.DictReader(f)

                for row in reader:
                    try:
                        product_id = row.get('id')
                        price = row.get('price')
                        discount_price = row.get('discount_price', '')

                        product = Product.objects.get(id=product_id)

                        if not dry_run:
                            product.price = Money(Decimal(price), target_currency)

                            if discount_price:
                                product.discount_price = Money(Decimal(discount_price), target_currency)

                            product.save()

                        self.stdout.write(f'  ✓ Updated product {product_id}: {price} {target_currency}')
                        updated += 1

                    except Product.DoesNotExist:
                        self.stdout.write(self.style.ERROR(f'  ✗ Product {product_id} not found'))
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f'  ✗ Error: {str(e)}'))

        except FileNotFoundError:
            raise CommandError(f'CSV file not found: {csv_file}')

        return updated