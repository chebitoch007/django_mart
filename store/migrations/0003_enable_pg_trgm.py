from django.db import migrations
from django.contrib.postgres.operations import TrigramExtension, BtreeGinExtension

class Migration(migrations.Migration):

    dependencies = [
        ('store', '0002_initial'),
    ]

    operations = [
        TrigramExtension(),
        BtreeGinExtension(),
    ]
