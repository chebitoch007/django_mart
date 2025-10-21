from django.db.models.signals import post_migrate, post_save, post_delete
from django.dispatch import receiver
from .models import Category, Review, Product
from store.constants import CATEGORIES
from django.db import transaction


@receiver(post_migrate)
def create_initial_categories(sender, **kwargs):
    if sender.name == 'store':
        with transaction.atomic():
            # Create parent categories
            for parent_name, children in CATEGORIES.items():
                # Create or get parent category
                parent_category, created = Category.objects.get_or_create(
                    name=parent_name,
                    parent=None,
                    defaults={'is_active': True}
                )

                if created:
                    print(f"Created parent category: {parent_name}")
                else:
                    print(f"Parent category exists: {parent_name}")

                # Create child categories
                for child_name in children.keys():
                    # Create or get child category
                    child_category, created = Category.objects.get_or_create(
                        name=child_name,
                        parent=parent_category,
                        defaults={'is_active': True}
                    )

                    if created:
                        print(f"Created child category: {child_name} under {parent_name}")
                    else:
                        print(f"Child category exists: {child_name} under {parent_name}")

            # Rebuild MPTT tree
            Category.objects.rebuild()
            print("Category tree rebuilt successfully")

def update_product_review_count(product):
    # Count only approved reviews
    count = Review.objects.filter(product=product, approved=True).count()
    Product.objects.filter(id=product.id).update(review_count=count)

@receiver(post_save, sender=Review)
def update_review_count_on_save(sender, instance, **kwargs):
    update_product_review_count(instance.product)

@receiver(post_delete, sender=Review)
def update_review_count_on_delete(sender, instance, **kwargs):
    update_product_review_count(instance.product)
