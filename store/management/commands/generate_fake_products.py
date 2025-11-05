# store/management/commands/generate_fake_products.py

import random
from django.core.management.base import BaseCommand
from store.models import Product, Category, Supplier
from decimal import Decimal


class Command(BaseCommand):
    help = 'Generate fake products for testing'

    PRODUCT_NAMES = {
        'gaming-chairs-desks': [
            'RGB Gaming Chair with Lumbar Support',
            'Ergonomic Gaming Desk with Cable Management',
            'Professional Gaming Chair - Racing Style',
            'Adjustable Standing Gaming Desk',
            'Premium Gaming Chair with Footrest',
        ],
        'keyboards-mice': [
            'Mechanical RGB Gaming Keyboard - 60%',
            'Wireless Gaming Mouse - 16000 DPI',
            'Hot-Swappable Mechanical Keyboard',
            'Ergonomic Wireless Mouse with Side Buttons',
            'TKL Mechanical Keyboard - Cherry MX',
            'RGB Gaming Mouse Pad - Extended',
        ],
    }

    DESCRIPTIONS = [
        'High-quality gaming product with premium materials and exceptional build quality. Features advanced ergonomics and customizable RGB lighting.',
        'Professional-grade equipment designed for serious gamers. Includes adjustable settings and durable construction.',
        'Feature-rich design with modern aesthetics. Perfect for extended gaming sessions and competitive play.',
        'Premium product with exceptional comfort and performance. Built to last with high-quality components.',
    ]

    def add_arguments(self, parser):
        parser.add_argument(
            '--count',
            type=int,
            default=10,
            help='Number of products to generate per category'
        )

    def handle(self, *args, **options):
        count = options['count']

        # Get or create supplier
        supplier, _ = Supplier.objects.get_or_create(
            name='AliExpress',
            defaults={
                'website': 'https://www.aliexpress.com',
                'notes': 'AliExpress dropshipping supplier'
            }
        )

        total_created = 0

        for category_slug, names in self.PRODUCT_NAMES.items():
            try:
                category = Category.objects.get(slug=category_slug)
            except Category.DoesNotExist:
                self.stdout.write(
                    self.style.WARNING(f'Category {category_slug} not found, skipping')
                )
                continue

            self.stdout.write(f'\nGenerating products for: {category.name}')

            for i in range(count):
                name = random.choice(names)
                # Make unique
                name = f'{name} - Model {random.randint(1000, 9999)}'

                description = random.choice(self.DESCRIPTIONS)

                # ✅ FIX: Convert to float first, then back to Decimal
                price = Decimal(str(random.uniform(15.0, 150.0))).quantize(Decimal('0.01'))

                # ✅ FIX: Convert price to float for the calculation
                discount = Decimal(str(random.uniform(10.0, float(price) - 5.0))).quantize(Decimal('0.01'))

                product = Product.objects.create(
                    category=category,
                    name=name,
                    description=description,
                    short_description=description[:150] + '...',
                    price=price,
                    discount_price=discount if random.random() > 0.5 else None,
                    stock=random.randint(10, 100),
                    available=True,
                    is_dropship=True,
                    supplier=supplier,
                    supplier_url=f'https://www.aliexpress.com/item/{random.randint(1000000000000, 9999999999999)}.html',
                    shipping_time='10-20 days',
                    commission_rate=15.0
                )

                total_created += 1
                self.stdout.write(
                    self.style.SUCCESS(f'  ✓ Created: {product.name} (${price})')
                )

        self.stdout.write(
            self.style.SUCCESS(f'\n✅ Generated {total_created} fake products!')
        )