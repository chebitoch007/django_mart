# store/management/commands/add_test_products.py

import random
from django.core.management.base import BaseCommand
from django.utils.text import slugify
from faker import Faker

from store.models import Category, Product, ProductImage, Supplier


class Command(BaseCommand):
    help = 'Adds test products to the database'

    def add_arguments(self, parser):
        parser.add_argument(
            'count', type=int, nargs='?', default=20,
            help='Number of products to create (default: 20)'
        )
        parser.add_argument(
            '--clear', action='store_true',
            help='Delete all existing products first'
        )

    def handle(self, *args, **options):
        fake = Faker()
        count = options['count']

        if options['clear']:
            self.stdout.write("Deleting all existing products (and related images)...")
            ProductImage.objects.all().delete()
            Product.objects.all().delete()

        categories = Category.objects.filter(is_active=True)
        if not categories.exists():
            self.stderr.write("No active categories found! Create categories first.")
            return

        self.stdout.write(f"Creating {count} test products...")

        for i in range(count):
            name = fake.catch_phrase()
            category = random.choice(categories)

            # Handle supplier as a ForeignKey to Supplier model
            supplier_obj = None
            if random.random() > 0.6:
                supplier_name = fake.company()
                supplier_obj, created = Supplier.objects.get_or_create(name=supplier_name)
                if created:
                    self.stdout.write(f"Created new Supplier: {supplier_name}")

            product = Product.objects.create(
                name=name,
                slug=slugify(name)[:200],
                description="\n\n".join(fake.paragraphs(nb=5)),
                short_description=fake.sentence(),
                price=round(random.uniform(5, 500), 2),
                discount_price=round(random.uniform(5, 300), 2) if random.random() > 0.7 else None,
                category=category,
                stock=random.randint(0, 100),
                available=(random.random() > 0.1),
                featured=(random.random() > 0.8),
                rating=round(random.uniform(1, 5), 2),
                review_count=random.randint(0, 50),
                is_dropship=(random.random() > 0.6),
                supplier=supplier_obj,
                shipping_time=f"{random.randint(3, 21)}-{random.randint(22, 30)} days"
            )

            # Add 1-4 product images
            for img_num in range(random.randint(1, 4)):
                ProductImage.objects.create(
                    product=product,
                    color=fake.color_name() if random.random() > 0.5 else ""
                )

            if (i + 1) % 10 == 0:
                self.stdout.write(f"Created {i + 1} products…")

        self.stdout.write(self.style.SUCCESS(f"Successfully created {count} test products!"))
