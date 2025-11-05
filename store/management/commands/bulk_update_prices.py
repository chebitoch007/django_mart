# store/management/commands/bulk_update_prices.py

import csv
from decimal import Decimal
from django.core.management.base import BaseCommand
from store.models import Product


class Command(BaseCommand):
    help = 'Bulk update product prices from a CSV file'

    def add_arguments(self, parser):
        parser.add_argument(
            'csv_file',
            type=str,
            help='Path to CSV file with columns: product_id,price,discount_price (optional)'
        )
        parser.add_argument(
            '--by-url',
            action='store_true',
            help='Use supplier_url instead of product_id for matching'
        )

    def handle(self, *args, **options):
        csv_file = options['csv_file']
        by_url = options['by_url']

        self.stdout.write(self.style.SUCCESS(f'Starting price update from {csv_file}'))

        success_count = 0
        fail_count = 0
        failed_items = []

        try:
            with open(csv_file, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)

                # Normalize field names (strip whitespace)
                fieldnames = [f.strip() for f in (reader.fieldnames or [])]

                # Validate required columns
                if by_url:
                    if 'url' not in fieldnames and 'supplier_url' not in fieldnames:
                        self.stdout.write(
                            self.style.ERROR('CSV must have "url" or "supplier_url" column when using --by-url')
                        )
                        return
                else:
                    if 'product_id' not in fieldnames and 'id' not in fieldnames:
                        self.stdout.write(
                            self.style.ERROR('CSV must have "product_id" or "id" column')
                        )
                        return

                if 'price' not in fieldnames:
                    self.stdout.write(
                        self.style.ERROR('CSV must have "price" column')
                    )
                    return

                for row_num, row in enumerate(reader, start=2):
                    try:
                        # Get identifier
                        if by_url:
                            identifier = row.get('url') or row.get('supplier_url', '').strip()
                            if not identifier:
                                self.stdout.write(
                                    self.style.WARNING(f'Row {row_num}: Missing URL, skipping')
                                )
                                fail_count += 1
                                continue

                            # Find product by URL
                            try:
                                product = Product.objects.get(supplier_url=identifier)
                            except Product.DoesNotExist:
                                self.stdout.write(
                                    self.style.ERROR(f'Row {row_num}: Product not found with URL: {identifier}')
                                )
                                failed_items.append({'identifier': identifier, 'reason': 'Product not found'})
                                fail_count += 1
                                continue
                        else:
                            identifier = row.get('product_id') or row.get('id', '').strip()
                            if not identifier:
                                self.stdout.write(
                                    self.style.WARNING(f'Row {row_num}: Missing product_id, skipping')
                                )
                                fail_count += 1
                                continue

                            # Find product by ID
                            try:
                                product = Product.objects.get(id=int(identifier))
                            except (Product.DoesNotExist, ValueError):
                                self.stdout.write(
                                    self.style.ERROR(f'Row {row_num}: Product not found with ID: {identifier}')
                                )
                                failed_items.append({'identifier': identifier, 'reason': 'Product not found'})
                                fail_count += 1
                                continue

                        # Get prices
                        price_str = row.get('price', '').strip()
                        discount_str = row.get('discount_price', '').strip()

                        if not price_str:
                            self.stdout.write(
                                self.style.WARNING(f'Row {row_num}: Missing price, skipping')
                            )
                            fail_count += 1
                            continue

                        # Update price
                        old_price = product.price
                        product.price = Decimal(price_str)

                        # Update discount price if provided
                        if discount_str:
                            product.discount_price = Decimal(discount_str)

                        product.save(update_fields=['price', 'discount_price', 'updated'])

                        self.stdout.write(
                            self.style.SUCCESS(
                                f'Row {row_num}: Updated {product.name[:50]} - '
                                f'${old_price} → ${product.price}'
                            )
                        )
                        success_count += 1

                    except Exception as e:
                        self.stdout.write(
                            self.style.ERROR(f'Row {row_num}: Error - {str(e)}')
                        )
                        failed_items.append({
                            'identifier': identifier,
                            'reason': str(e)
                        })
                        fail_count += 1

        except FileNotFoundError:
            self.stdout.write(
                self.style.ERROR(f'File not found: {csv_file}')
            )
            return
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error reading file: {str(e)}')
            )
            return

        # Summary
        self.stdout.write('\n' + '=' * 60)
        self.stdout.write(self.style.SUCCESS(f'\nPrice Update Complete!'))
        self.stdout.write(f'✓ Successful updates: {success_count}')
        self.stdout.write(f'✗ Failed updates: {fail_count}')
        self.stdout.write(f'Total processed: {success_count + fail_count}\n')

        # Show failed items
        if failed_items:
            self.stdout.write(self.style.WARNING('\nFailed Items:'))
            for item in failed_items:
                self.stdout.write(f'  • {item["identifier"]}')
                self.stdout.write(f'    Reason: {item["reason"]}\n')