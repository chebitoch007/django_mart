from celery import shared_task
from django.core.mail import send_mail
from .models import PaymentLog

@shared_task(max_retries=3, default_retry_delay=300)
def process_webhook_retry(webhook_id):
    try:
        webhook = PaymentLog.objects.get(id=webhook_id)
        # Reprocess webhook logic
        # ...
        webhook.status = 'PROCESSED'
        webhook.save()
    except Exception as e:
        # Notify admins after final retry failure
        send_mail(
            'Webhook Processing Failed',
            f'Webhook ID: {webhook_id}\nError: {str(e)}',
            'alerts@yourstore.com',
            ['admin@yourstore.com'],
            fail_silently=False
        )
        raise self.retry(exc=e)