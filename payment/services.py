import logging
import random
import time
from django.conf import settings
from .models import Payment

logger = logging.getLogger(__name__)


class PaymentProcessor:
    def __init__(self, payment):
        self.payment = payment
        self.method = payment.method
        self.amount = payment.amount
        self.currency = payment.currency
        self.user = payment.order.user
        self.payment_method = payment.payment_method

    def process(self):
        """Process payment based on method"""
        self.payment.mark_as_processing()

        try:
            if self.method in ['MPESA', 'AIRTEL']:
                return self.process_mobile_money()
            elif self.method in ['VISA', 'MASTERCARD']:
                return self.process_card()
            elif self.method == 'PAYPAL':
                return self.process_paypal()
            else:
                return self.error_result("Unsupported payment method")
        except Exception as e:
            logger.error(f"Payment processing failed: {str(e)}")
            return self.error_result("Payment processing error")

    def process_mobile_money(self):
        """Process mobile money payment"""
        # In production, this would call the mobile money API
        # Simulate API call
        time.sleep(2)

        # Simulate success 90% of the time
        if random.random() < 0.9:
            # Generate verification code
            verification_code = self.payment.generate_verification_code()

            # In production, send code via SMS
            logger.info(f"Mobile money verification code: {verification_code}")

            # Set payment deadline
            self.payment.set_payment_deadline(hours=24)

            return {
                'success': True,
                'verification_required': True,
                'verification_code': verification_code
            }
        else:
            return self.error_result("Mobile money payment failed")

    def process_card(self):
        """Process card payment"""
        # In production, this would call Stripe or another payment gateway
        # Simulate API call
        time.sleep(2)

        # Simulate success 95% of the time
        if random.random() < 0.95:
            self.payment.mark_as_paid()
            return {'success': True}
        else:
            return self.error_result("Card payment failed")

    def process_paypal(self, email=None):
        """Process PayPal payment"""
        # In production, this would call PayPal API
        # Simulate API call
        time.sleep(3)

        # Simulate success 90% of the time
        if random.random() < 0.9:
            self.payment.mark_as_paid()
            return {'success': True}
        else:
            return self.error_result("PayPal payment failed")

    def error_result(self, message, code="PAYMENT_FAILED"):
        return {
            'success': False,
            'error_code': code,
            'error_message': message
        }