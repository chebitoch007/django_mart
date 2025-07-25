from django.db import models, transaction
from django.core.validators import MinValueValidator, RegexValidator
from django.utils import timezone
import secrets
from .constants import PAYMENT_METHODS, CURRENCY_CHOICES

from django.conf import settings
from cryptography.fernet import Fernet
import logging
import uuid

logger = logging.getLogger(__name__)


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
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='payment_app_payment_methods'
    )
    # Encrypted card details
    encrypted_card_number = models.CharField(max_length=255)
    encrypted_expiry_date = models.CharField(max_length=255)
    encrypted_cvv = models.CharField(max_length=255)
    cardholder_name = models.CharField(max_length=100)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Card metadata
    card_type = models.CharField(
        max_length=20,
        choices=[('visa', 'Visa'), ('mastercard', 'MasterCard'),
                 ('amex', 'American Express'), ('other', 'Other')]
    )
    last_4_digits = models.CharField(max_length=4, editable=False)
    expiration_month = models.PositiveIntegerField(editable=False)
    expiration_year = models.PositiveIntegerField(editable=False)

    # Audit fields
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = "Payment Methods"
        ordering = ['-is_default', '-created_at']

    def __str__(self):
        return f"{self.card_type} ending in {self.last_4_digits}"

    def save(self, *args, **kwargs):
        # Encrypt sensitive data before saving
        if not self.pk:  # Only on creation
            self.last_4_digits = self.encrypted_card_number[-4:]

            # Parse expiration date
            expiry_date = self.encrypted_expiry_date
            self.expiration_month = int(expiry_date[:2])
            self.expiration_year = int(expiry_date[3:])

            # Encrypt all sensitive data
            encryptor = EncryptionManager()
            self.encrypted_card_number = encryptor.encrypt(self.encrypted_card_number)
            self.encrypted_expiry_date = encryptor.encrypt(self.encrypted_expiry_date)
            self.encrypted_cvv = encryptor.encrypt(self.encrypted_cvv)

        super().save(*args, **kwargs)

    def get_decrypted_card_number(self):
        """Decrypt card number for processing"""
        encryptor = EncryptionManager()
        return encryptor.decrypt(self.encrypted_card_number)

    def get_decrypted_expiry_date(self):
        """Decrypt expiry date for processing"""
        encryptor = EncryptionManager()
        return encryptor.decrypt(self.encrypted_expiry_date)

    def get_decrypted_cvv(self):
        """Decrypt CVV for processing (use with extreme caution)"""
        encryptor = EncryptionManager()
        return encryptor.decrypt(self.encrypted_cvv)

    def clean(self):
        """Validate payment method data"""
        if self.is_default:
            # Check if another default exists
            existing_default = PaymentMethod.objects.filter(
                user=self.user,
                is_default=True
            ).exclude(pk=self.pk).exists()

            if existing_default:
                raise ValidationError(
                    _('User already has a default payment method'),
                    code='duplicate_default'
                )

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)



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