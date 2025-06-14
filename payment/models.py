from django.db import models, transaction
from django.conf import settings
from django.core.validators import MinValueValidator
from django.utils import timezone
import secrets
from .constants import PAYMENT_METHODS, CURRENCY_CHOICES
from django.core.validators import FileExtensionValidator
from PIL import Image

class Payment(models.Model):
    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
        ('REFUNDED', 'Refunded'),
    )

    order = models.OneToOneField(
        'orders.Order',
        on_delete=models.CASCADE,
        related_name='payment'
    )
    method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHODS,
        db_index=True
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING',
        db_index=True
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0.01)]
    )
    currency = models.CharField(
        max_length=3,
        choices=CURRENCY_CHOICES,
        default='KES'
    )
    verification_code = models.CharField(max_length=8, blank=True)
    payment_deadline = models.DateTimeField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    transaction_id = models.CharField(max_length=50, blank=True, unique=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'method']),
            models.Index(fields=['payment_deadline']),
        ]
        verbose_name = "Payment"
        verbose_name_plural = "Payments"

    def __str__(self):
        return f"Payment #{self.id} - {self.get_status_display()} ({self.amount})"

    def generate_verification_code(self):
        """Generate cryptographically secure verification code"""
        self.verification_code = secrets.token_urlsafe(6).upper()[:8]
        self.full_clean()
        self.save()
        return self.verification_code

    def set_payment_deadline(self, hours=48):
        """Set payment deadline with validation"""
        if hours < 1 or hours > 168:
            raise ValueError("Payment window must be between 1-168 hours")
        self.payment_deadline = timezone.now() + timezone.timedelta(hours=hours)
        self.save()

    @property
    def formatted_amount(self):
        return f"{self.get_currency_display()} {self.amount:,.2f}"

    @property
    def is_active(self):
        return self.status == 'PENDING' and timezone.now() < self.payment_deadline
    @property
    def time_remaining(self):
        return self.payment_deadline - timezone.now()

    @property
    def is_active(self):
        return self.status == 'PENDING' and self.time_remaining.total_seconds() > 0

    @transaction.atomic
    def mark_as_paid(self):
        self.status = 'COMPLETED'
        self.is_paid = True
        self.save(update_fields=['status', 'is_paid'])

    def verify_code(self, code):
        if not self.is_active:
            return False
        if self.verification_code == code.strip().upper():
            self.mark_as_paid()
            return True
        return False

    def get_provider_display(self):
        pass


class PaymentVerificationCode(models.Model):
    payment = models.ForeignKey(
        Payment,
        on_delete=models.CASCADE,
        related_name='verification_codes'
    )
    code = models.CharField(max_length=8, unique=True)
    is_used = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(db_index=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['expires_at', 'is_used']),
        ]

    def __str__(self):
        return f"Code {self.code} for Payment #{self.payment_id}"

    @property
    def is_valid(self):
        return not self.is_used and timezone.now() < self.expires_at

    def mark_used(self):
        self.is_used = True
        self.save(update_fields=['is_used', 'expires_at'])