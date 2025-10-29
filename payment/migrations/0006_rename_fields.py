from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ('payment', '0005_auto_20251028_2024'),
    ]

    operations = [
        migrations.RenameField(
            model_name='payment',
            old_name='amount',
            new_name='old_amount',
        ),
        migrations.RenameField(
            model_name='payment',
            old_name='currency',
            new_name='old_currency',
        ),
        migrations.RenameField(
            model_name='payment',
            old_name='original_amount',
            new_name='old_original_amount',
        ),
        migrations.RenameField(
            model_name='payment',
            old_name='converted_amount',
            new_name='old_converted_amount',
        ),
    ]
