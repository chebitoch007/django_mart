import csv
import os
import json
from django.core.management.base import BaseCommand
from store.aliexpress import import_aliexpress_product


class Command(BaseCommand):
    help = 'Import products from AliExpress into the store'

    def add_arguments(self, parser):
        parser.add_argument('--json', type=str, help='Path to JSON import file')
        parser.add_argument('--csv', type=str, help='Path to CSV import file')  # Add this line
        parser.add_argument('--url', type=str, help='Single product URL to import')
        parser.add_argument('--category', type=str, help='Category for single product import')

    def handle(self, *args, **options):
        if options['json']:
            self.import_from_json(options['json'])
        elif options['csv']:  # Add CSV handling
            self.import_from_csv(options['csv'])
        elif options['url'] and options['category']:
            self.import_single_product(options['url'], options['category'])
        else:
            self.stdout.write(self.style.ERROR('Invalid arguments. Use --json, --csv, or --url with --category'))


    def import_from_json(self, json_path):
        try:
            # Resolve relative paths
            if not os.path.isabs(json_path):
                json_path = os.path.join(os.getcwd(), json_path)

            if not os.path.exists(json_path):
                raise FileNotFoundError(f"File not found: {json_path}")

            with open(json_path, 'r') as f:
                products = json.load(f)

            if not isinstance(products, list):
                raise ValueError("JSON file should contain a list of products")

            success_count = 0
            for i, product in enumerate(products, 1):
                if not isinstance(product, dict):
                    self.stdout.write(self.style.WARNING(f"Skipping item #{i}: Not a dictionary"))
                    continue

                url = product.get('url')
                category = product.get('category')

                if not url or not category:
                    self.stdout.write(self.style.WARNING(
                        f"Skipping item #{i}: Missing URL or category"))
                    continue

                result, message = import_aliexpress_product(url, category)
                if result:
                    self.stdout.write(self.style.SUCCESS(
                        f"Imported #{i}: {result.name} (ID: {result.id})"))
                    success_count += 1
                else:
                    self.stdout.write(self.style.WARNING(
                        f"Failed #{i}: {url} - {message}"))

            self.stdout.write(self.style.SUCCESS(
                f"\nImported {success_count}/{len(products)} products successfully"
            ))
            return success_count

        except FileNotFoundError as e:
            self.stdout.write(self.style.ERROR(str(e)))
            self.stdout.write(self.style.WARNING(
                "Current directory: " + os.getcwd()))
        except json.JSONDecodeError:
            self.stdout.write(self.style.ERROR("Invalid JSON format in file"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error processing JSON: {str(e)}"))

    def import_from_csv(self, csv_path):  # Add this function
        try:
            with open(csv_path, 'r') as f:
                reader = csv.DictReader(f)
                products = []
                for row in reader:
                    products.append({
                        'url': row['url'],
                        'category': row['category']
                    })
                self._import_products(products)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error processing CSV: {str(e)}"))

    def _import_products(self, products):  # Helper function
        success_count = 0
        for product in products:
            result, message = import_aliexpress_product(
                product['url'],
                product['category']
            )
            if result:
                self.stdout.write(self.style.SUCCESS(f"Imported: {result.name}"))
                success_count += 1
            else:
                self.stdout.write(self.style.WARNING(f"Failed: {product['url']} - {message}"))

        total = len(products)
        self.stdout.write(self.style.SUCCESS(
            f"\nImported {success_count}/{total} products successfully"
        ))

    def import_single_product(self, url, category):
        try:
            self.stdout.write(f"Importing product from: {url}")
            product, message = import_aliexpress_product(url, category)
            if product:
                self.stdout.write(self.style.SUCCESS(
                    f"Successfully imported: {product.name} (ID: {product.id})"
                ))
                return product
            else:
                self.stdout.write(self.style.ERROR(f"Import failed: {message}"))
                return None
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error: {str(e)}"))
            return None