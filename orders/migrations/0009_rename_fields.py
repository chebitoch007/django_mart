from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0008_auto_20251028_2024'),  # 👈 replace with your actual previous migration
    ]

    operations = [
        migrations.RenameField(
            model_name='order',
            old_name='total',
            new_name='old_total',
        ),
        migrations.RenameField(
            model_name='order',
            old_name='currency',
            new_name='old_currency',
        ),
        migrations.RenameField(
            model_name='orderitem',
            old_name='price',
            new_name='old_price',
        ),
    ]
