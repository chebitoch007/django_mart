#payment/models.py

from typing import Any
from django.db import models
from django.conf import settings
from djmoney.models.fields import MoneyField
from django.core.exceptions import ValidationError
from orders.constants import ORDER_STATUS_CHOICES
from orders.models import Order


class Payment(models.Model):
    PROVIDER_CHOICES = (
        ('MPESA', 'M-Pesa'),
        ('PAYPAL', 'PayPal'),
    )

    order = models.OneToOneField(
        Order,
        on_delete=models.CASCADE,
        related_name='payment'
    )
    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES, default='M-Pesa')
    status = models.CharField(max_length=20, choices=ORDER_STATUS_CHOICES, default='PENDING', db_index=True)
    amount = MoneyField(
        max_digits=10,
        decimal_places=2,
        default_currency=settings.DEFAULT_CURRENCY,
        default=0.00  # <-- ADD THIS LINE
    )
    transaction_id = models.CharField(max_length=255, blank=True)
    phone_number = models.CharField(max_length=15, blank=True)
    paypal_email = models.EmailField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    raw_response = models.JSONField(blank=True, null=True)
    original_amount = MoneyField(
        max_digits=10, decimal_places=2, null=True, blank=True, default_currency=None
    )
    converted_amount = MoneyField(
        max_digits=10, decimal_places=2, null=True, blank=True, default_currency=None
    )
    exchange_rate = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    checkout_request_id = models.CharField(max_length=255, blank=True, null=True, unique=True, db_index=True)
    result_code = models.CharField(max_length=10, blank=True)
    result_description = models.TextField(blank=True)
    retry_count = models.PositiveIntegerField(default=0)
    last_retry_at = models.DateTimeField(null=True, blank=True)
    failure_type = models.CharField(
        max_length=20,
        choices=[
            ('TEMPORARY', 'Temporary Failure (Retryable)'),
            ('USER_CANCELLED', 'Cancelled by User'),
            ('PERMANENT', 'Permanent Failure'),
            ('TIMEOUT', 'Timeout')
        ],
        blank=True
    )

    def __str__(self):
        return f"{self.provider} Payment - {self.status}"

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['order', 'provider'],
                name='unique_order_provider',
                condition=models.Q(status__in=['PENDING', 'PROCESSING'])
            )
        ]

    def clean(self):
        if self.status in ['PENDING', 'PROCESSING']:
            existing = Payment.objects.filter(
                order=self.order,
                provider=self.provider,
                status__in=['PENDING', 'PROCESSING']
            ).exclude(pk=self.pk)
            if existing.exists():
                raise ValidationError(
                    f"An active {self.provider} payment already exists for this order"
                )
