# store/management/commands/remove_test_products.py

from django.core.management.base import BaseCommand
from store.models import Product, ProductImage, Supplier, Brand, Review
from django.db import transaction


class Command(BaseCommand):
    help = "Removes test data created by the add_test_products command."

    def add_arguments(self, parser):
        parser.add_argument(
            '--suppliers', action='store_true',
            help='Also delete test suppliers created by Faker.'
        )
        parser.add_argument(
            '--brands', action='store_true',
            help='Also delete brands (if any test brands were generated).'
        )
        parser.add_argument(
            '--reviews', action='store_true',
            help='Also delete reviews associated with test products.'
        )
        parser.add_argument(
            '--confirm', action='store_true',
            help='Bypass confirmation prompt (use for automation).'
        )

    @transaction.atomic
    def handle(self, *args, **options):
        confirm = options['confirm']

        if not confirm:
            confirm_input = input(
                "⚠️ This will permanently delete ALL test products, related images, "
                "and optionally suppliers/brands/reviews. Continue? (yes/no): "
            )
            if confirm_input.lower() != 'yes':
                self.stdout.write(self.style.WARNING("Operation cancelled."))
                return

        # Delete reviews (optional)
        if options['reviews']:
            count_reviews = Review.objects.count()
            Review.objects.all().delete()
            self.stdout.write(f"🗑️ Deleted {count_reviews} reviews.")

        # Delete product images
        count_images = ProductImage.objects.count()
        ProductImage.objects.all().delete()
        self.stdout.write(f"🗑️ Deleted {count_images} product images.")

        # Delete products
        count_products = Product.objects.count()
        Product.objects.all().delete()
        self.stdout.write(f"🗑️ Deleted {count_products} products.")

        # Delete suppliers if requested
        if options['suppliers']:
            count_suppliers = Supplier.objects.count()
            Supplier.objects.all().delete()
            self.stdout.write(f"🗑️ Deleted {count_suppliers} suppliers.")

        # Delete brands if requested
        if options['brands']:
            count_brands = Brand.objects.count()
            Brand.objects.all().delete()
            self.stdout.write(f"🗑️ Deleted {count_brands} brands.")

        self.stdout.write(self.style.SUCCESS("✅ Test data removal complete."))
