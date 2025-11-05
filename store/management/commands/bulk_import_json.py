# store/management/commands/bulk_import_json.py

import json
import time
from django.core.management.base import BaseCommand
from store.aliexpress import import_aliexpress_product
from store.models import Category
from django.utils.text import slugify


class Command(BaseCommand):
    help = 'Bulk import products from AliExpress using a JSON file'

    def add_arguments(self, parser):
        parser.add_argument(
            'json_file',
            type=str,
            help='Path to JSON file with array of {url, category} objects'
        )
        parser.add_argument(
            '--delay',
            type=int,
            default=5,
            help='Delay between imports in seconds (default: 5)'
        )

    def handle(self, *args, **options):
        json_file = options['json_file']
        delay = options['delay']

        self.stdout.write(self.style.SUCCESS(f'Starting bulk import from {json_file}'))
        self.stdout.write(f'Delay between imports: {delay} seconds\n')

        success_count = 0
        fail_count = 0
        failed_products = []

        try:
            with open(json_file, 'r', encoding='utf-8') as file:
                products = json.load(file)

            if not isinstance(products, list):
                self.stdout.write(
                    self.style.ERROR('JSON must be an array of objects with "url" and "category" fields')
                )
                return

            for idx, item in enumerate(products, start=1):
                url = item.get('url', '').strip()
                category_name = item.get('category', '').strip()

                if not url or not category_name:
                    self.stdout.write(
                        self.style.WARNING(f'Item {idx}: Missing URL or category, skipping')
                    )
                    self.stdout.write(f'  URL: "{url}"')
                    self.stdout.write(f'  Category: "{category_name}"\n')
                    fail_count += 1
                    continue

                # Convert category name to slug
                category_slug = slugify(category_name)

                # Check if category exists
                try:
                    category = Category.objects.get(slug=category_slug)
                except Category.DoesNotExist:
                    # Try to find by name (case-insensitive)
                    category = Category.objects.filter(name__iexact=category_name).first()

                    if not category:
                        self.stdout.write(
                            self.style.ERROR(
                                f'Item {idx}: Category "{category_name}" (slug: {category_slug}) not found, skipping'
                            )
                        )
                        failed_products.append({
                            'url': url,
                            'reason': f'Category not found: {category_name}'
                        })
                        fail_count += 1
                        continue

                self.stdout.write(f'\n[Item {idx}] Importing: {url}')
                self.stdout.write(f'     Category: {category.name} (slug: {category.slug})')

                try:
                    product, message = import_aliexpress_product(url, category.slug)

                    if product:
                        self.stdout.write(
                            self.style.SUCCESS(f'     ✓ Success: {product.name} (ID: {product.id})')
                        )
                        success_count += 1
                    else:
                        self.stdout.write(
                            self.style.ERROR(f'     ✗ Failed: {message}')
                        )
                        failed_products.append({
                            'url': url,
                            'reason': message
                        })
                        fail_count += 1

                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f'     ✗ Error: {str(e)}')
                    )
                    failed_products.append({
                        'url': url,
                        'reason': str(e)
                    })
                    fail_count += 1

                # Delay to avoid rate limiting (not on last item)
                if idx < len(products):
                    self.stdout.write(f'     Waiting {delay} seconds...')
                    time.sleep(delay)

        except FileNotFoundError:
            self.stdout.write(
                self.style.ERROR(f'File not found: {json_file}')
            )
            return
        except json.JSONDecodeError as e:
            self.stdout.write(
                self.style.ERROR(f'Invalid JSON file: {str(e)}')
            )
            return
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error reading file: {str(e)}')
            )
            return

        # Summary
        self.stdout.write('\n' + '=' * 60)
        self.stdout.write(self.style.SUCCESS(f'\nImport Complete!'))
        self.stdout.write(f'✓ Successful imports: {success_count}')
        self.stdout.write(f'✗ Failed imports: {fail_count}')
        self.stdout.write(f'Total processed: {success_count + fail_count}\n')

        # Show failed products
        if failed_products:
            self.stdout.write(self.style.WARNING('\nFailed Products:'))
            for item in failed_products:
                self.stdout.write(f'  • {item["url"]}')
                self.stdout.write(f'    Reason: {item["reason"]}\n')