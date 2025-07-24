from django.db.models.signals import post_save
from django.dispatch import receiver
from orders.models import Order
from .models import Payment

@receiver(post_save, sender=Order)
def create_order_payment(sender, instance, created, **kwargs):
    if created and not hasattr(instance, 'payment'):
        Payment.objects.create(
            order=instance,
            amount=instance.total_price,
            currency=instance.currency,
            status='PENDING'
        )

@receiver(post_save, sender=Order)
def create_payment_record(sender, instance, created, **kwargs):
    if created:
        Payment.objects.create(
            order=instance,
            method=instance.payment_method,
            amount=instance.total_cost,
            currency=instance.currency
        )
