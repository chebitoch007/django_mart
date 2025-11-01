from django.db import migrations

def forward_normalize_supplier_brand(apps, schema_editor):
    Product = apps.get_model('store', 'Product')
    Supplier = apps.get_model('store', 'Supplier')
    Brand = apps.get_model('store', 'Brand')

    # Safely migrate existing plain text supplier_name into Supplier table
    for product in Product.objects.all():
        # Only run if supplier_name exists in DB row
        supplier_name = getattr(product, 'supplier_name', None)
        if supplier_name:
            supplier, _ = Supplier.objects.get_or_create(name=supplier_name.strip())
            product.supplier = supplier
            product.save(update_fields=['supplier'])

        # Same for brand if exists
        brand_name = getattr(product, 'search_brand', None)
        if brand_name:
            brand, _ = Brand.objects.get_or_create(name=brand_name.strip())
            product.brand = brand
            product.save(update_fields=['brand'])

def backward_normalize_supplier_brand(apps, schema_editor):
    # No rollback necessary
    pass

class Migration(migrations.Migration):

    dependencies = [
        ('store', '0004_brand_supplier_product_search_brand_and_more'),
    ]

    operations = [
        migrations.RunPython(forward_normalize_supplier_brand, backward_normalize_supplier_brand),
    ]