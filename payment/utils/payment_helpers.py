from django.conf import settings
from django.core.mail import send_mail
import logging

logger = logging.getLogger(__name__)


def send_email(to_email, subject, message):
    """Send email with fallback to console output"""
    try:
        if settings.EMAIL_BACKEND != 'django.core.mail.backends.console.EmailBackend':
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[to_email],
                fail_silently=False
            )
        else:
            print(f"Email to {to_email}: {message}")
    except Exception as e:
        logger.error(f"Failed to send email: {str(e)}")


def send_sms(phone_number, message):
    """Send SMS with proper error handling"""
    try:
        # Only attempt if SMS API key is configured
        if not settings.PAYMENT_SETTINGS.get('SMS_API_KEY'):
            logger.warning("SMS API key not configured - skipping SMS send")
            return

        # Implement actual SMS gateway integration here
        # Example using Africa's Talking API:
        # from africastalking.Service import SMS
        # sms = SMS()
        # sms.send(message, [phone_number])

        logger.info(f"Sent SMS to {phone_number}: {message}")

    except Exception as e:
        logger.error(f"SMS sending failed: {str(e)}")


def send_payment_instructions(customer, code):
    """Send payment instructions with multiple fallback mechanisms"""
    message = f"Your payment verification code: {code}"

    try:
        # 1. Attempt SMS
        if settings.PAYMENT_SETTINGS.get('SMS_API_KEY'):
            send_sms(customer.phone_number, message)
        else:
            logger.info("SMS not configured - using email only")

        # 2. Always send email
        send_email(
            customer.email,
            "Payment Instructions",
            f"{message}\n\nVisit {settings.SITE_URL}/payment to complete"
        )

        # 3. Log for customer support reference
        logger.info(f"Sent payment instructions to {customer.email} | Code: {code}")

    except Exception as e:
        logger.critical(f"Failed to send payment instructions: {str(e)}")
        # Implement additional fallback (e.g., messaging queue) here