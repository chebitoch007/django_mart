
# payment/signals.py

# from django.db.models.signals import post_save
# from django.dispatch import receiver
# from orders.models import Order
# from payment.models import Payment
# import logging
#
#
#
# logger = logging.getLogger(__name__)
#
#
# @receiver(post_save, sender=Order)
# def create_payment_for_order(sender, instance, created, **kwargs):
#     """Create a payment record when an order is created"""
#     if created:
#         Payment.objects.create(
#             order=instance,
#             amount=instance.total_cost, # This was also inconsistent with create_order
#             provider='MPESA',
#             status='PENDING',
#             transaction_id=None,
#             checkout_request_id=None,
#             mpesa_receipt_number=None,
#             raw_response=None,
#         )