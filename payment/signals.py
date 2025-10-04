from django.db.models.signals import post_save
from django.dispatch import receiver
from paypal.standard.ipn.signals import valid_ipn_received, invalid_ipn_received
from django.db import transaction
import json
from orders.models import Order
from payment.models import Payment
import logging



logger = logging.getLogger(__name__)





@receiver(valid_ipn_received)

def paypal_payment_received(sender, **kwargs):

    """Handle valid PayPal IPN signals"""

    ipn_obj = sender



    try:

        custom_data = json.loads(ipn_obj.custom) if ipn_obj.custom else {}

        order_id = custom_data.get('order_id')



        if not order_id:

            logger.error("No order ID in PayPal IPN")

            return



        with transaction.atomic():

            order = Order.objects.select_for_update().get(id=order_id)

            payment, created = Payment.objects.get_or_create(

                order=order,

                provider='PAYPAL',

                defaults={

                    'amount': ipn_obj.mc_gross,

                    'currency': ipn_obj.mc_currency,

                    'status': 'PENDING'

                }

            )



            if ipn_obj.payment_status == "Completed":

                # Check if this is a duplicate transaction

                if payment.status == 'COMPLETED':

                    logger.info(f"Payment already completed for order {order_id}")

                    return



                # Update payment and order

                payment.status = 'COMPLETED'

                payment.transaction_id = ipn_obj.txn_id

                payment.raw_response = {

                    'ipn_data': {

                        'payment_status': ipn_obj.payment_status,

                        'payer_email': ipn_obj.payer_email,

                        'receiver_email': ipn_obj.receiver_email,

                        'mc_gross': ipn_obj.mc_gross,

                        'mc_currency': ipn_obj.mc_currency,

                    }

                }

                payment.save()



                # Update order

                order.status = 'PAID'

                order.payment_method = 'PAYPAL'

                order.save()



                logger.info(f"PayPal payment completed for order {order_id}")



            elif ipn_obj.payment_status == "Pending":

                payment.status = 'PROCESSING'

                payment.save()

                logger.info(f"PayPal payment pending for order {order_id}")



            elif ipn_obj.payment_status in ["Failed", "Denied"]:

                payment.status = 'FAILED'

                payment.failure_type = 'PAYPAL_' + ipn_obj.payment_status

                payment.save()

                logger.warning(f"PayPal payment failed for order {order_id}")



    except Order.DoesNotExist:

        logger.error(f"Order not found for PayPal IPN: {order_id}")

    except Exception as e:

        logger.exception(f"Error processing PayPal IPN: {str(e)}")





@receiver(invalid_ipn_received)

def paypal_payment_invalid(sender, **kwargs):

    """Handle invalid PayPal IPN signals"""

    logger.warning("Invalid PayPal IPN received")

@receiver(post_save, sender=Order)

def create_payment_for_order(sender, instance, created, **kwargs):

    """Create a payment record when an order is created"""

    if created:

        Payment.objects.create(

            order=instance,

            amount=instance.total_cost,

            provider='MPESA'  # Default provider

        )