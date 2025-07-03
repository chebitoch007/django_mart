from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.core.validators import MinValueValidator, RegexValidator
from django.utils import timezone
import secrets
from django.utils.translation import gettext_lazy as _

from django.conf import settings
from cryptography.fernet import Fernet
import logging
import uuid

logger = logging.getLogger(__name__)

PAYMENT_METHOD_TYPES = (
    ('MPESA', 'M-Pesa'),
    ('AIRTEL', 'Airtel Money'),
    ('VISA', 'Visa'),
    ('MASTERCARD', 'MasterCard'),
    ('PAYPAL', 'PayPal'),
)

PAYMENT_PROVIDER_CHOICES = (
    ('MPESA', 'M-Pesa'),
    ('AIRTEL', 'Airtel Money'),
    ('VISA', 'Visa'),
    ('MASTERCARD', 'MasterCard'),
    ('PAYPAL', 'PayPal'),
)

PAYMENT_STATUS_CHOICES = (
    ('PENDING', 'Pending'),
    ('COMPLETED', 'Completed'),
    ('FAILED', 'Failed'),
    ('REFUNDED', 'Refunded'),
    ('PROCESSING', 'Processing'),
)

CURRENCY_CHOICES = (
    ('USD', 'US Dollar'),
    ('EUR', 'Euro'),
    ('GBP', 'British Pound'),
    ('KES', 'Kenyan Shilling'),
    ('UGX', 'Ugandan Shilling'),
    ('TZS', 'Tanzanian Shilling'),
)


class EncryptionManager:
    """Handles encryption/decryption of sensitive fields"""

    def __init__(self):
        self.cipher = Fernet(settings.FIELD_ENCRYPTION_KEY)

    def encrypt(self, value):
        return self.cipher.encrypt(value.encode()).decode()

    def decrypt(self, encrypted_value):
        return self.cipher.decrypt(encrypted_value.encode()).decode()


class PaymentMethod(models.Model):
    """Secure payment method storage with encryption"""
    method_type = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD_TYPES,
        default='VISA'
    )
    paypal_email = models.EmailField(blank=True, null=True)
    paypal_token = models.CharField(max_length=255, blank=True, null=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='payment_methods'
    )

    # Card fields
    encrypted_card_number = models.CharField(max_length=255, blank=True, null=True)
    encrypted_expiry_date = models.CharField(max_length=255, blank=True, null=True)
    encrypted_cvv = models.CharField(max_length=255, blank=True, null=True)
    cardholder_name = models.CharField(max_length=100, blank=True, null=True)

    # Mobile money fields
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    provider_code = models.CharField(max_length=20, blank=True, null=True)

    # Common fields
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Card metadata
    card_type = models.CharField(
        max_length=20,
        choices=[('visa', 'Visa'), ('mastercard', 'MasterCard'), ('amex', 'American Express'), ('other', 'Other')],
        blank=True,
        null=True
    )
    last_4_digits = models.CharField(max_length=4, blank=True, null=True)
    expiration_month = models.PositiveIntegerField(blank=True, null=True)
    expiration_year = models.PositiveIntegerField(blank=True, null=True)

    # Audit fields
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = "Payment Methods"
        ordering = ['-is_default', '-created_at']
        unique_together = ('user', 'is_default')

    def __str__(self):
        if self.method_type in ['VISA', 'MASTERCARD']:
            return f"{self.get_method_type_display()} ending in {self.last_4_digits}"
        elif self.method_type == 'PAYPAL':
            return f"PayPal: {self.paypal_email}"
        else:
            return f"{self.get_method_type_display()}: {self.phone_number}"

    def save(self, *args, **kwargs):
        # Encrypt sensitive data before saving
        encryptor = EncryptionManager()

        # Card data encryption
        if self.encrypted_card_number and not self.pk:
            self.last_4_digits = self.encrypted_card_number[-4:]
            self.encrypted_card_number = encryptor.encrypt(self.encrypted_card_number)

        if self.encrypted_expiry_date and not self.pk:
            expiry_date = self.encrypted_expiry_date
            self.expiration_month = int(expiry_date[:2])
            self.expiration_year = int(expiry_date[3:])
            self.encrypted_expiry_date = encryptor.encrypt(self.encrypted_expiry_date)

        if self.encrypted_cvv and not self.pk:
            self.encrypted_cvv = encryptor.encrypt(self.encrypted_cvv)

        # PayPal token encryption
        if self.paypal_token and not self.pk:
            self.paypal_token = encryptor.encrypt(self.paypal_token)

        # Set only one default method
        if self.is_default:
            PaymentMethod.objects.filter(user=self.user, is_default=True).exclude(pk=self.pk).update(is_default=False)

        super().save(*args, **kwargs)

    def get_decrypted_paypal_token(self):
        if self.paypal_token:
            encryptor = EncryptionManager()
            return encryptor.decrypt(self.paypal_token)
        return None

    def get_decrypted_card_number(self):
        """Decrypt card number for processing"""
        if self.encrypted_card_number:
            encryptor = EncryptionManager()
            return encryptor.decrypt(self.encrypted_card_number)
        return None

    def get_decrypted_expiry_date(self):
        """Decrypt expiry date for processing"""
        if self.encrypted_expiry_date:
            encryptor = EncryptionManager()
            return encryptor.decrypt(self.encrypted_expiry_date)
        return None

    def get_decrypted_cvv(self):
        """Decrypt CVV for processing (use with extreme caution)"""
        if self.encrypted_cvv:
            encryptor = EncryptionManager()
            return encryptor.decrypt(self.encrypted_cvv)
        return None


class Payment(models.Model):
    order = models.OneToOneField(
        'orders.Order',
        on_delete=models.CASCADE,
        related_name='payment'
    )
    method = models.CharField(
        max_length=20,
        choices=PAYMENT_PROVIDER_CHOICES,
        db_index=True
    )
    status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
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
        default='USD'
    )
    verification_code = models.CharField(max_length=8, blank=True, null=True)
    payment_deadline = models.DateTimeField(db_index=True, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    transaction_id = models.CharField(max_length=50, blank=True, unique=True)

    # Payment method reference
    payment_method = models.ForeignKey(
        PaymentMethod,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    # Gateway response
    gateway_response = models.JSONField(null=True, blank=True)
    gateway_transaction_id = models.CharField(max_length=255, blank=True, null=True)

    # Error handling
    error_code = models.CharField(max_length=50, blank=True, null=True)
    error_message = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'method']),
            models.Index(fields=['payment_deadline']),
        ]
        verbose_name = "Payment"
        verbose_name_plural = "Payments"

    def __str__(self):
        return f"Payment #{self.id} - {self.get_status_display()} ({self.amount} {self.currency})"

    def generate_verification_code(self):
        """Generate cryptographically secure verification code"""
        self.verification_code = secrets.token_urlsafe(6).upper()[:8]
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
    def time_remaining(self):
        if self.payment_deadline:
            return self.payment_deadline - timezone.now()
        return None

    @property
    def is_active(self):
        return self.status == 'PENDING' and self.payment_deadline and timezone.now() < self.payment_deadline

    @transaction.atomic
    def mark_as_paid(self):
        self.status = 'COMPLETED'
        self.save(update_fields=['status'])

    @transaction.atomic
    def mark_as_failed(self, error_code=None, error_message=None):
        self.status = 'FAILED'
        self.error_code = error_code
        self.error_message = error_message
        self.save(update_fields=['status', 'error_code', 'error_message'])

    @transaction.atomic
    def mark_as_processing(self):
        self.status = 'PROCESSING'
        self.save(update_fields=['status'])

    def verify_code(self, code):
        if not self.is_active:
            return False
        if self.verification_code and self.verification_code == code.strip().upper():
            self.mark_as_paid()
            return True
        return False


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
        self.save(update_fields=['is_used'])