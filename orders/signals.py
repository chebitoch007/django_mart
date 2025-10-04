from .models import Order
from payment.models import Payment
from django.db.models.signals import post_save
from django.dispatch import receiver



@receiver(post_save, sender=Order)
def handle_order_creation(sender, instance, created, **kwargs):
    if created:
        # Create payment transaction
        Payment.objects.create(
            order=instance,
            amount=instance.total_cost,
            currency=instance.currency,
            original_amount=instance.total_cost,
            converted_amount=instance.total_cost,
            phone_number=instance.phone,
            status='pending'
        )

        # Send order confirmation email
        from django.core.mail import send_mail
        send_mail(
            f'Order #{instance.id} Confirmation',
            f'Your order has been received and is being processed. Total amount: {instance.total_cost} {instance.currency}',
            'asai@gmail.com',
            [instance.email],
            fail_silently=True,
        )

