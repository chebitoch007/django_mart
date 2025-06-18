from django.apps import AppConfig



class StoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'store'

    def ready(self):
        # Register MPTT models
        from mptt import register as mptt_register
        from .models import Category
        mptt_register(Category)
