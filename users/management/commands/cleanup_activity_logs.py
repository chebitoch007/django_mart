from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from users.models import ActivityLog
from django.conf import settings


class Command(BaseCommand):
    help = 'Delete activity logs older than specified retention period'

    def handle(self, *args, **options):
        retention_days = getattr(settings, 'ACTIVITY_LOG_RETENTION_DAYS', 90)
        cutoff_date = timezone.now() - timedelta(days=retention_days)

        deleted_count, _ = ActivityLog.objects.filter(
            timestamp__lt=cutoff_date
        ).delete()

        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully deleted {deleted_count} activity logs older than {retention_days} days'
            )
        )