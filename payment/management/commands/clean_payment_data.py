from datetime import timedelta

from django.core.management.base import BaseCommand
from payment.models import Payment
from django.utils import timezone


class Command(BaseCommand):
    help = 'Cleans old payment data'

    def handle(self, *args, **options):
        # Keep successful payments for 7 years (legal requirement)
        # Delete failed payments after 6 months
        cutoff = timezone.now() - timedelta(days=180)
        Payment.objects.filter(
            status__in=['FAILED', 'PENDING'],
            created_at__lt=cutoff
        ).delete()