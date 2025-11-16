#payment/models.py

import uuid
from django.db import models
from django.conf import settings
from djmoney.models.fields import MoneyField
from orders.constants import ORDER_STATUS_CHOICES
from orders.models import Order


class Payment(models.Model):
    PROVIDER_CHOICES = (
        ('MPESA', 'M-Pesa'),
        ('PAYPAL', 'PayPal'),
        ('PAYSTACK', 'Paystack'),
    )

    # Core fields
    order = models.OneToOneField(
        Order,
        on_delete=models.CASCADE,
        related_name='payment'
    )
    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES, default='MPESA')
    status = models.CharField(max_length=20, choices=ORDER_STATUS_CHOICES, default='PENDING', db_index=True)

    # ✅ NEW: Idempotency key to prevent duplicate processing
    idempotency_key = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)

    # Amount fields
    amount = MoneyField(
        max_digits=10,
        decimal_places=2,
        default_currency=settings.DEFAULT_CURRENCY,
        default=0.00
    )
    original_amount = MoneyField(
        max_digits=10, decimal_places=2, null=True, blank=True, default_currency=None
    )
    converted_amount = MoneyField(
        max_digits=10, decimal_places=2, null=True, blank=True, default_currency=None
    )
    exchange_rate = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)

    # Transaction tracking
    transaction_id = models.CharField(max_length=255, blank=True, db_index=True)
    checkout_request_id = models.CharField(max_length=255, blank=True, null=True, unique=True, db_index=True)

    # Contact info
    phone_number = models.CharField(max_length=15, blank=True)
    paypal_email = models.EmailField(blank=True)

    # Response data
    raw_response = models.JSONField(blank=True, null=True)
    result_code = models.CharField(max_length=10, blank=True)
    result_description = models.TextField(blank=True)

    # Retry logic
    retry_count = models.PositiveIntegerField(default=0)
    last_retry_at = models.DateTimeField(null=True, blank=True)
    failure_type = models.CharField(
        max_length=20,
        choices=[
            ('TEMPORARY', 'Temporary Failure (Retryable)'),
            ('USER_CANCELLED', 'Cancelled by User'),
            ('PERMANENT', 'Permanent Failure'),
            ('TIMEOUT', 'Timeout'),
            ('DUPLICATE', 'Duplicate Payment'),
            ('STOCK_ISSUE', 'Stock Validation Failed'),
        ],
        blank=True
    )

    # ✅ NEW: Processing lock to prevent race conditions
    processing_locked = models.BooleanField(default=False)
    locked_at = models.DateTimeField(null=True, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.provider} Payment - Order #{self.order.id} - {self.status}"

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'provider']),
            models.Index(fields=['checkout_request_id']),
            models.Index(fields=['transaction_id']),
        ]

    # ✅ NEW: Helper methods for safe state transitions
    def can_process(self):
        """Check if payment can be processed"""
        return self.status in ['PENDING', 'PROCESSING'] and not self.processing_locked

    def mark_processing(self):
        """Mark payment as being processed"""
        from django.utils import timezone
        self.processing_locked = True
        self.locked_at = timezone.now()
        self.status = 'PROCESSING'
        self.save(update_fields=['processing_locked', 'locked_at', 'status'])

    def release_lock(self):
        """Release processing lock"""
        self.processing_locked = False
        self.locked_at = None
        self.save(update_fields=['processing_locked', 'locked_at'])