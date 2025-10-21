import threading
import logging
from django.core.mail import send_mail
from django.conf import settings

logger = logging.getLogger(__name__)


def send_email_async(subject, message, recipient, html_message=None):
    def send():
        try:
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [recipient],
                html_message=html_message,
                fail_silently=False
            )
        except Exception as e:
            logger.error(f"Failed to send email: {str(e)}", exc_info=True)

    thread = threading.Thread(target=send)
    thread.start()