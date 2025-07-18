import requests
import stripe
from requests.exceptions import RequestException

from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.core.validators import MinValueValidator, RegexValidator
from django.utils import timezone
import secrets

from encrypted_model_fields.fields import EncryptedCharField


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
    ('REFUND_PENDING', 'Refund Pending'),
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

        if self.encrypted_card_number:
            # Extract last 4 digits before encryption
            self.last_4_digits = str(self.encrypted_card_number)[-4:]
            self.encrypted_card_number = encryptor.encrypt(str(self.encrypted_card_number))

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

        # Prevent setting inactive methods as default
        if self.is_default and not self.is_active:
            raise ValidationError("Inactive payment methods cannot be set as default")

        # PCI Compliance: Never store CVV long-term
        if self.pk and self.method_type in ['VISA', 'MASTERCARD']:
            original = PaymentMethod.objects.get(pk=self.pk)
            if original.encrypted_cvv and not self.encrypted_cvv:
                self.encrypted_cvv = None  # Remove CVV after initial use

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


class StripeRefundService:
    def __init__(self):
        stripe.api_key = settings.STRIPE_SECRET_KEY

    def process(self, transaction_id, amount):
        try:
            # Convert amount to cents
            amount_cents = int(amount * 100)

            # Create refund
            refund = stripe.Refund.create(
                payment_intent=transaction_id,
                amount=amount_cents,
                reason='requested_by_customer'
            )

            if refund.status == 'succeeded':
                return {
                    'success': True,
                    'refund_id': refund.id,
                    'status': refund.status
                }
            else:
                return {
                    'success': False,
                    'error_code': 'REFUND_FAILED',
                    'error_message': f'Refund status: {refund.status}'
                }

        except stripe.error.StripeError as e:
            logger.error(f"Stripe refund error: {e.user_message}")
            return {
                'success': False,
                'error_code': e.code,
                'error_message': e.user_message
            }
        except Exception as e:
            logger.exception("Unexpected Stripe refund error")
            return {
                'success': False,
                'error_code': 'STRIPE_ERROR',
                'error_message': str(e)
            }


class MobileMoneyRefundService:
    def _get_access_token(self, provider):
        auth_url = settings.MPESA_AUTH_URL if provider == 'MPESA' else settings.AIRTEL_AUTH_URL
        credentials = {
            'MPESA': (settings.MPESA_CONSUMER_KEY, settings.MPESA_CONSUMER_SECRET),
            'AIRTEL': (settings.AIRTEL_CLIENT_ID, settings.AIRTEL_CLIENT_SECRET)
        }

        try:
            response = requests.get(
                auth_url,
                auth=credentials[provider],
                timeout=10
            )
            response.raise_for_status()
            return response.json().get('access_token')
        except RequestException as e:
            logger.error(f"{provider} auth failed: {str(e)}")
            return None

    def _initiate_refund(self, provider, token, transaction_id, amount):
        url = settings.MPESA_REFUND_URL if provider == 'MPESA' else settings.AIRTEL_REFUND_URL
        payload = {
            "TransactionID": transaction_id,
            "Amount": amount,
            "Currency": "KES",
            "Reference": f"REFUND-{transaction_id}",
            "Reason": "Customer request"
        }

        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }

        try:
            response = requests.post(
                url,
                json=payload,
                headers=headers,
                timeout=15
            )
            response.raise_for_status()
            return response.json()
        except RequestException as e:
            logger.error(f"{provider} refund API error: {str(e)}")
            return None

    def process(self, transaction_id, amount):
        # Determine provider from transaction ID prefix
        provider = 'MPESA' if transaction_id.startswith('MPE') else 'AIRTEL'

        # Get access token
        token = self._get_access_token(provider)
        if not token:
            return {
                'success': False,
                'error_code': 'AUTH_FAILED',
                'error_message': 'Could not authenticate with payment gateway'
            }

        # Initiate refund
        result = self._initiate_refund(provider, token, transaction_id, amount)

        if result and result.get('ResponseCode') == '0':
            return {
                'success': True,
                'refund_id': result.get('RefundTransactionID'),
                'status': 'Initiated'  # Mobile money refunds are typically async
            }
        else:
            error_msg = result.get('ResponseDescription') if result else 'Refund request failed'
            return {
                'success': False,
                'error_code': 'REFUND_FAILED',
                'error_message': error_msg
            }


class PayPalRefundService:
    def _get_access_token(self):
        try:
            response = requests.post(
                settings.PAYPAL_TOKEN_URL,
                auth=(settings.PAYPAL_CLIENT_ID, settings.PAYPAL_SECRET),
                data={'grant_type': 'client_credentials'},
                headers={'Accept': 'application/json'},
                timeout=10
            )
            response.raise_for_status()
            return response.json().get('access_token')
        except RequestException as e:
            logger.error(f"PayPal auth failed: {str(e)}")
            return None

    def process(self, transaction_id, amount):
        token = self._get_access_token()
        if not token:
            return {
                'success': False,
                'error_code': 'AUTH_FAILED',
                'error_message': 'Could not authenticate with PayPal'
            }

        url = f"{settings.PAYPAL_API_URL}/v2/payments/captures/{transaction_id}/refund"
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {token}',
            'Prefer': 'return=representation'
        }

        payload = {
            "amount": {
                "value": str(amount),
                "currency_code": "USD"  # PayPal typically uses USD
            },
            "note_to_payer": "Refund per customer request"
        }

        try:
            response = requests.post(
                url,
                json=payload,
                headers=headers,
                timeout=15
            )

            if response.status_code == 201:
                data = response.json()
                return {
                    'success': True,
                    'refund_id': data['id'],
                    'status': data['status']
                }
            else:
                error_data = response.json()
                return {
                    'success': False,
                    'error_code': error_data.get('name', 'REFUND_FAILED'),
                    'error_message': error_data.get('message', 'PayPal refund failed')
                }

        except RequestException as e:
            logger.error(f"PayPal refund API error: {str(e)}")
            return {
                'success': False,
                'error_code': 'API_ERROR',
                'error_message': 'Could not connect to PayPal'
            }


class RefundServiceFactory:
    @staticmethod
    def get_service(method):
        method = method.upper()
        if method in ['VISA', 'MASTERCARD']:
            return StripeRefundService()
        elif method in ['MPESA', 'AIRTEL']:
            return MobileMoneyRefundService()
        elif method == 'PAYPAL':
            return PayPalRefundService()
        raise ValueError(f"Unsupported refund method: {method}")


class Payment(models.Model):
    order = models.OneToOneField(
        'orders.Order',  # Use string reference
        on_delete=models.CASCADE,
        related_name='payment_relation'
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

    refund_requested = models.BooleanField(default=False)
    refund_requested_at = models.DateTimeField(null=True, blank=True)
    refund_processed_at = models.DateTimeField(null=True, blank=True)
    refund_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0.01)]
    )
    refund_reason = models.TextField(blank=True, null=True)

    # Encrypt sensitive fields
    phone_number = EncryptedCharField(max_length=20)
    card_last4 = EncryptedCharField(max_length=4)

    # Idempotency key to prevent duplicate processing
    idempotency_key = models.CharField(max_length=36, unique=True, blank=True, null=True)

    # Fraud detection flags
    is_suspicious = models.BooleanField(default=False)
    fraud_score = models.FloatField(default=0.0)

    # PCI Compliance: Remove sensitive data after processing
    def clean_sensitive_data(self):
        if self.status in ['COMPLETED', 'FAILED']:
            self.encrypted_cvv = None
            self.encrypted_card_number = None
            self.save(update_fields=['encrypted_cvv', 'encrypted_card_number'])

    @transaction.atomic
    def process_refund(self):
        """Process approved refund with actual gateway"""
        if not self.refund_requested:
            raise ValidationError("Refund not requested")

        try:
            # Get refund service based on payment method
            refund_service = RefundServiceFactory.get_service(self.method)
            result = refund_service.process(
                self.gateway_transaction_id,
                self.refund_amount
            )

            if result['success']:
                self.status = 'REFUNDED'
                self.refund_processed_at = timezone.now()
                self.save()
                return True
            return False
        except Exception as e:
            logger.error(f"Refund failed for {self.id}: {str(e)}")
            return False

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

    @transaction.atomic
    def request_refund(self, amount, reason):
        """Initiate refund request"""
        if amount > self.amount:
            raise ValidationError("Refund amount cannot exceed original payment")

        self.refund_requested = True
        self.refund_requested_at = timezone.now()
        self.refund_amount = amount
        self.refund_reason = reason
        self.status = 'REFUND_PENDING'
        self.save()

    @transaction.atomic
    def process_refund(self):
        """Process approved refund"""
        if not self.refund_requested:
            raise ValidationError("Refund not requested")

        self.status = 'REFUNDED'
        self.refund_processed_at = timezone.now()
        self.save()

    def clean(self):
        # Validate payment method against order
        if self.payment_method and self.payment_method.user != self.order.user:
            raise ValidationError("Payment method does not belong to order owner")

    def save(self, *args, **kwargs):
        # Generate unique transaction ID
        if not self.transaction_id:
            self.transaction_id = f"TX-{uuid.uuid4().hex[:12].upper()}"

        # Set currency based on order
        if not self.currency:
            self.currency = self.order.currency

        # Remove sensitive data after processing
        if self.status in ['COMPLETED', 'FAILED']:
            self.encrypted_cvv = None
            self.encrypted_card_number = None

        super().save(*args, **kwargs)


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


class CurrencyExchangeRate(models.Model):
    base_currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES)
    target_currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES)
    rate = models.DecimalField(max_digits=12, decimal_places=6)
    last_updated = models.DateTimeField(auto_now=True)


class PaymentGatewaySettings(models.Model):
    provider = models.CharField(max_length=50, unique=True)
    is_active = models.BooleanField(default=True)
    priority = models.PositiveIntegerField(default=1)
    supported_countries = models.JSONField(default=list)
    supported_currencies = models.JSONField(default=list)


class PaymentLog(models.Model):
    """Audit log for all payment activities"""
    LOG_TYPES = (
        ('CREATED', 'Payment Created'),
        ('PROCESSING', 'Processing Started'),
        ('SUCCESS', 'Payment Succeeded'),
        ('FAILED', 'Payment Failed'),
        ('REFUND', 'Refund Processed'),
        ('WEBHOOK', 'Webhook Received'),
    )

    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name='logs')
    log_type = models.CharField(max_length=20, choices=LOG_TYPES)
    details = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['created_at', 'log_type'])]

    def __str__(self):
        return f"{self.get_log_type_display()} - {self.payment_id}"