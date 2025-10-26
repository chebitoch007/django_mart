#orders/signals.py

from .models import Order
from django.db.models.signals import post_save
from django.dispatch import receiver
import logging

logger = logging.getLogger(__name__)

@receiver(post_save, sender=Order)
def handle_order_creation(sender, instance, created, **kwargs):
    if created:
        # ----------------------------------------------------
        # The Payment creation logic is (correctly) removed.
        #
        # The email logic has been moved to a Celery task
        # in the create_order view. This is more reliable
        # as it runs *after* the order items and payment
        # objects are fully associated.
        # ----------------------------------------------------
        logger.info(f"Order #{instance.id} created. Email task will be queued.")
        pass