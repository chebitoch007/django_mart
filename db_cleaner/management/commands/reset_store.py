from django.core.management.base import BaseCommand
from store.models import Product, Category, ProductImage, Review
from orders.models import Order, OrderItem
from cart.models import Cart, CartItem
from django.db import transaction


class Command(BaseCommand):
    help = 'Resets store-related data while preserving users and settings'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force reset without confirmation'
        )

    def handle(self, *args, **options):
        force = options['force']

        if not force:
            confirm = input("⚠️  WARNING: This will delete ALL store data. Continue? [y/N] ")
            if confirm.lower() != 'y':
                self.stdout.write(self.style.WARNING('Operation cancelled'))
                return

        with transaction.atomic():
            # Delete in proper order to avoid foreign key issues
            self.stdout.write("Deleting cart items...")
            CartItem.objects.all().delete()

            self.stdout.write("Deleting carts...")
            Cart.objects.all().delete()

            self.stdout.write("Deleting order items...")
            OrderItem.objects.all().delete()

            self.stdout.write("Deleting orders...")
            Order.objects.all().delete()

            self.stdout.write("Deleting reviews...")
            Review.objects.all().delete()

            self.stdout.write("Deleting product images...")
            ProductImage.objects.all().delete()

            self.stdout.write("Deleting products...")
            Product.objects.all().delete()

            # Preserve the default category
            self.stdout.write("Resetting categories...")
            Category.objects.exclude(slug='default-category').delete()

            self.stdout.write(self.style.SUCCESS('Successfully reset store data!'))
            self.stdout.write("You can now import new products using:")
            self.stdout.write("python3 manage.py import_aliexpress --csv=product_imports.csv")