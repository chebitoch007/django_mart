# orders/migrations/0005_update_country_codes.py
from django.db import migrations

# mapping of existing values to correct codes
COUNTRY_MAP = {
    'Kenya': 'KE',
    # add any other values in your DB if there are more
}

def update_country_codes(apps, schema_editor):
    Order = apps.get_model('orders', 'Order')
    for old_value, new_code in COUNTRY_MAP.items():
        Order.objects.filter(country=old_value).update(country=new_code)

class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0005_alter_order_country'),  # adjust to correct last migration
    ]

    operations = [
        migrations.RunPython(update_country_codes),
    ]
