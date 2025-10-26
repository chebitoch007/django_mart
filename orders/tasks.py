#orders/tasks.py

from celery import shared_task
from django.core.management import call_command
from .models import Order
from django.core.mail import send_mail
from django.conf import settings

@shared_task
def update_exchange_rates():
    call_command('update_exchange_rates')


@shared_task
def order_created_email(order_id):
    """
    Task to send an e-mail notification when an order is
    successfully created.
    """
    try:
        order = Order.objects.get(id=order_id)
        subject = f'Order #{order.id} Confirmation - Thank You!'
        message = (
            f'Dear {order.get_full_name()},\n\n'
            f'Your order has been successfully placed.\n'
            f'Your order ID is: {order.id}\n'
            f'Total amount: {order.total} {order.currency}\n\n'
            f'We will notify you once your order is being processed.'
            f'\n\nThank you for shopping with us!'
        )
        mail_sent = send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [order.email],
            fail_silently=False,
        )
        return mail_sent
    except Order.DoesNotExist:
        return None