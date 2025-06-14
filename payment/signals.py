from django.db.models.signals import post_save
from django.dispatch import receiver
from orders.models import Order
from .models import Payment


@receiver(post_save, sender=Order)
def create_payment_record(sender, instance, created, **kwargs):
    if created:
        Payment.objects.create(
            order=instance,
            method=instance.payment_method,
            amount=instance.total_cost,
            currency=instance.currency
        )
