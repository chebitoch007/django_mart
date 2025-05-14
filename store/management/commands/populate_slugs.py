from django.core.management.base import BaseCommand
from store.models import Product


class Command(BaseCommand):
    help = 'Populates slug field for existing products'

    def handle(self, *args, **options):
        products = Product.objects.filter(slug__isnull=True)
        for product in products:
            product.save()  # This triggers the save() method that generates the slug
            self.stdout.write(f'Updated slug for {product.name}')

        self.stdout.write(self.style.SUCCESS('Successfully populated all slugs'))