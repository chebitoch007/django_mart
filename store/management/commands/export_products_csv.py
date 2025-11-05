# store/management/commands/export_products_csv.py

import csv
from django.core.management.base import BaseCommand
from store.models import Product


class Command(BaseCommand):
    help = 'Export products to CSV for bulk editing'

    def add_arguments(self, parser):
        parser.add_argument(
            'output_file',
            type=str,
            help='Output CSV file path'
        )
        parser.add_argument(
            '--dropship-only',
            action='store_true',
            help='Export only dropship products'
        )
        parser.add_argument(
            '--category',
            type=str,
            help='Filter by category slug'
        )

    def handle(self, *args, **options):
        output_file = options['output_file']
        dropship_only = options['dropship_only']
        category = options['category']

        self.stdout.write(self.style.SUCCESS(f'Exporting products to {output_file}'))

        # Build query
        products = Product.objects.all().select_related('category', 'supplier')

        if dropship_only:
            products = products.filter(is_dropship=True)

        if category:
            products = products.filter(category__slug=category)

        products = products.order_by('category__name', 'name')

        try:
            with open(output_file, 'w', encoding='utf-8', newline='') as file:
                writer = csv.writer(file)

                # Write header
                writer.writerow([
                    'product_id',
                    'name',
                    'category',
                    'supplier_url',
                    'price',
                    'discount_price',
                    'stock',
                    'available'
                ])

                # Write products
                count = 0
                for product in products:
                    writer.writerow([
                        product.id,
                        product.name,
                        product.category.name if product.category else '',
                        product.supplier_url or '',
                        str(product.price.amount),
                        str(product.discount_price.amount) if product.discount_price else '',
                        product.stock,
                        'yes' if product.available else 'no'
                    ])
                    count += 1

            self.stdout.write(
                self.style.SUCCESS(f'\n✅ Exported {count} products to {output_file}')
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f'\nYou can now edit prices in the CSV and import with:\n'
                    f'python manage.py bulk_update_prices {output_file}'
                )
            )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error writing file: {str(e)}')
            )