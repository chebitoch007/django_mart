# orders/tasks.py - FIXED VERSION

from celery import shared_task
from django.core.management import call_command
from .models import Order
from django.core.mail import send_mail
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


@shared_task
def update_exchange_rates():
    """Update exchange rates from external API"""
    call_command('update_exchange_rates')


@shared_task
def order_created_email(order_id):
    """
    Task to send an e-mail notification when an order is successfully created.
    """
    try:
        order = Order.objects.get(id=order_id)

        # Format currency correctly
        amount = order.total.amount
        currency = order.total.currency

        subject = f'Order #{order.id} Confirmation - Thank You!'
        message = (
            f'Dear {order.get_full_name()},\n\n'
            f'Your order has been successfully placed.\n'
            f'Your order ID is: {order.id}\n'
            f'Total amount: {currency} {amount}\n\n'
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

        logger.info(f"Order confirmation email sent for order #{order.id}")
        return mail_sent

    except Order.DoesNotExist:
        logger.error(f"Order {order_id} not found for email notification")
        return None
    except Exception as e:
        logger.error(f"Failed to send order email for {order_id}: {str(e)}")
        return None