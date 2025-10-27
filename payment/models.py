from typing import Any  #payment/models.py
from django.db import models
from pydantic_core import ValidationError
from orders.constants import CURRENCY_CHOICES, ORDER_STATUS_CHOICES
from paypal.standard.ipn.models import PayPalIPN
from django.db.models.signals import post_save
from django.dispatch import receiver
from orders.models import Order


class Payment(models.Model):

    PROVIDER_CHOICES = (
        ('MPESA', 'M-Pesa'),
        ('PAYPAL', 'PayPal'),
    )
    order = models.OneToOneField(
        Order,
        on_delete=models.CASCADE,
        related_name='payment'  # Use a simple related_name
    )

    provider = models.CharField(
        max_length=20,
        choices=PROVIDER_CHOICES,
        default='M-Pesa'
    )
    status = models.CharField(max_length=20, choices=ORDER_STATUS_CHOICES, default='PENDING',db_index=True )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    transaction_id = models.CharField(max_length=255, blank=True)
    phone_number = models.CharField(max_length=15, blank=True)  # For MPesa
    paypal_email = models.EmailField(blank=True)  # For PayPal
    created_at = models.DateTimeField(auto_now_add=True)
    raw_response = models.JSONField(blank=True, null=True)  # Store gateway responses
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default='KES')
    original_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    converted_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
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

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)  # <-- unpack correctly

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
        """Prevent duplicate active payments for the same order"""
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
