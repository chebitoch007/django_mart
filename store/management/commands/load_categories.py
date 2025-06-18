from django.core.management.base import BaseCommand
from django.utils.text import slugify
from store.models import Category
from store.constants import CATEGORIES


class Command(BaseCommand):
    help = 'Load initial categories into the database'

    def handle(self, *args, **options):
        for parent_name, children in CATEGORIES.items():
            parent, _ = Category.objects.get_or_create(
                name=parent_name,
                defaults={'slug': slugify(parent_name), 'is_active': True}
            )

            for child_name in children:
                Category.objects.get_or_create(
                    name=child_name,
                    parent=parent,
                    defaults={'slug': slugify(child_name), 'is_active': True}
                )

        self.stdout.write(self.style.SUCCESS('Successfully loaded categories'))