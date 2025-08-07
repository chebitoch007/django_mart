import random
from django.core.management.base import BaseCommand
from django.utils.text import slugify
from store.models import Category, Product, ProductImage
from faker import Faker
from django.templatetags.static import static



class Command(BaseCommand):
    help = 'Adds test products to the database'

    def add_arguments(self, parser):
        parser.add_argument('count', type=int, nargs='?', default=20,
                            help='Number of products to create (default: 20)')
        parser.add_argument('--clear', action='store_true',
                            help='Delete all existing products first')

    def handle(self, *args, **options):
        fake = Faker()
        count = options['count']

        if options['clear']:
            self.stdout.write("Deleting all existing products...")
            Product.objects.all().delete()

        # Get all active categories
        categories = Category.objects.filter(is_active=True)
        if not categories:
            self.stderr.write("No active categories found! Create categories first.")
            return

        self.stdout.write(f"Creating {count} test products...")

        for i in range(count):
            # Create product with realistic data
            name = fake.catch_phrase()
            category = random.choice(categories)

            product = Product.objects.create(
                name=name,
                slug=slugify(name)[:200],
                description=fake.paragraphs(nb=5, ext_word_list=None),
                short_description=fake.sentence(),
                price=random.uniform(5, 500),
                discount_price=random.uniform(5, 300) if random.random() > 0.7 else None,
                category=category,
                stock=random.randint(0, 100),
                available=random.random() > 0.1,
                featured=random.random() > 0.8,
                rating=random.uniform(1, 5),
                review_count=random.randint(0, 50),
                is_dropship=random.random() > 0.6,
                supplier=fake.company() if random.random() > 0.6 else "",
                shipping_time=f"{random.randint(3, 21)}-{random.randint(22, 30)} days"
            )

            # Add 1-4 product images
            for img_num in range(random.randint(1, 4)):
                ProductImage.objects.create(
                    product=product,
                    color=fake.color_name() if random.random() > 0.5 else ""
                )

            if (i + 1) % 10 == 0:
                self.stdout.write(f"Created {i + 1} products...")

        self.stdout.write(self.style.SUCCESS(f"Successfully created {count} test products!"))

def get_image_url(self):
    if self.image and self.image.name:
        return self.image.url
    return static('store/images/placeholder.png')  # Add default placeholder