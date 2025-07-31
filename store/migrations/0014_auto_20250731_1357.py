from django.db import migrations
from django.db.models import Count  # Add this import


def clean_category_names(apps, schema_editor):
    Category = apps.get_model('store', 'Category')

    for category in Category.objects.all():
        # Remove emojis from category names
        clean_name = ''.join(char for char in category.name if char.isalnum() or char.isspace())
        if clean_name != category.name:
            print(f"Renaming '{category.name}' to '{clean_name}'")
            category.name = clean_name
            category.save(update_fields=['name'])


def remove_duplicate_categories(apps, schema_editor):
    Category = apps.get_model('store', 'Category')

    # Find duplicate categories at same level
    duplicates = Category.objects.values('name', 'parent').annotate(
        count=Count('id')  # Use Count from django.db.models
    ).filter(count__gt=1)

    for dup in duplicates:
        categories = Category.objects.filter(name=dup['name'], parent_id=dup['parent']).order_by('id')
        # Keep the first instance, delete others
        for category in categories[1:]:
            print(f"Deleting duplicate category: {category.name} (ID: {category.id})")
            category.delete()


class Migration(migrations.Migration):
    dependencies = [
        ('store', '0013_alter_category_image'),
    ]

    operations = [
        migrations.RunPython(clean_category_names),
        migrations.RunPython(remove_duplicate_categories),
    ]