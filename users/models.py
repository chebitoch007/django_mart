from django.contrib.auth.models import AbstractUser
from django.db import models
from django.conf import settings
from django.urls import reverse
from django.utils import timezone
from django.core.validators import RegexValidator, FileExtensionValidator
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.hashers import make_password
from PIL import Image
from django_countries.fields import CountryField
import uuid
import re
from cryptography.fernet import Fernet
import os
import logging

logger = logging.getLogger(__name__)

# Kenyan counties list
KENYAN_COUNTIES = [
    ('Nairobi', 'Nairobi'), ('Mombasa', 'Mombasa'), ('Kisumu', 'Kisumu'), ('Nakuru', 'Nakuru'),
    ('Eldoret', 'Eldoret'), ('Thika', 'Thika'), ('Malindi', 'Malindi'), ('Kitale', 'Kitale'),
    ('Kakamega', 'Kakamega'), ('Kisii', 'Kisii'), ('Garissa', 'Garissa'), ('Wajir', 'Wajir'),
    ('Mandera', 'Mandera'), ('Marsabit', 'Marsabit'), ('Isiolo', 'Isiolo'), ('Meru', 'Meru'),
    ('Nyeri', 'Nyeri'), ('Embu', 'Embu'), ('Machakos', 'Machakos'), ('Kitui', 'Kitui'),
    ('Makueni', 'Makueni'), ('Nyandarua', 'Nyandarua'), ('Nandi', 'Nandi'), ('Bomet', 'Bomet'),
    ('Kericho', 'Kericho'), ('Bungoma', 'Bungoma'), ('Busia', 'Busia'), ('Siaya', 'Siaya'),
    ('Homa Bay', 'Homa Bay'), ('Migori', 'Migori'), ('Kilifi', 'Kilifi'), ('Kwale', 'Kwale'),
    ('Lamu', 'Lamu'), ('Taita Taveta', 'Taita Taveta'), ('Trans Nzoia', 'Trans Nzoia'),
    ('Uasin Gishu', 'Uasin Gishu'), ('Elgeyo-Marakwet', 'Elgeyo-Marakwet'), ('West Pokot', 'West Pokot'),
    ('Samburu', 'Samburu'), ('Turkana', 'Turkana'), ('Laikipia', 'Laikipia'),
    ('Muranga', 'Muranga'), ('Kirinyaga', 'Kirinyaga'), ('Vihiga', 'Vihiga'),
    ('Baringo', 'Baringo'), ('Narok', 'Narok')
]


class EncryptionManager:
    """Handles encryption/decryption of sensitive fields"""

    def __init__(self):
        self.cipher = Fernet(settings.FIELD_ENCRYPTION_KEY)

    def encrypt(self, value):
        return self.cipher.encrypt(value.encode()).decode()

    def decrypt(self, encrypted_value):
        return self.cipher.decrypt(encrypted_value.encode()).decode()


class CustomUserManager(models.Manager):
    """Custom manager with security methods"""

    def create_user(self, username, email, password, **extra_fields):
        # Enforce strong passwords
        self._validate_password(password)
        user = self.model(
            username=username,
            email=self.normalize_email(email),
            **extra_fields
        )
        user.set_password(password)
        user.save(using=self._db)
        return user

    def _validate_password(self, password):
        """Enforce strong password policy"""
        if len(password) < 10:
            raise ValidationError("Password must be at least 10 characters long")
        if not re.search(r'[A-Z]', password):
            raise ValidationError("Password must contain at least one uppercase letter")
        if not re.search(r'[a-z]', password):
            raise ValidationError("Password must contain at least one lowercase letter")
        if not re.search(r'[0-9]', password):
            raise ValidationError("Password must contain at least one digit")
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            raise ValidationError("Password must contain at least one special character")


class CustomUser(AbstractUser):
    # Security enhancements
    objects = CustomUserManager()

    # Consent Management (GDPR/Data Protection Act 2019 Kenya)
    consent_date = models.DateTimeField(default=timezone.now)
    terms_accepted = models.BooleanField(
        default=False,
        verbose_name="Accepted Terms of Service"
    )
    terms_accepted_date = models.DateTimeField(null=True, blank=True)
    privacy_accepted = models.BooleanField(
        default=False,
        verbose_name="Accepted Privacy Policy"
    )
    privacy_accepted_date = models.DateTimeField(null=True, blank=True)
    consent_version = models.CharField(
        max_length=20,
        default="1.0",
        verbose_name="Policy Version"
    )

    # Unique identifier for public-facing systems
    public_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    # Contact Information (Kenyan-focused)
    phone_regex = RegexValidator(
        regex=r'^\+?254\d{9}$',
        message="Phone number must be in the format: '+2547XXXXXXXX'"
    )
    phone_number = models.CharField(
        max_length=20,
        validators=[phone_regex],
        blank=True,
        verbose_name="Phone Number"
    )
    phone_verified = models.BooleanField(default=False)
    email_verified = models.BooleanField(default=False)

    # Address Information
    county = models.CharField(
        max_length=50,
        blank=True,
        choices=KENYAN_COUNTIES
    )
    town = models.CharField(max_length=100, blank=True)
    postal_address = models.CharField(max_length=100, blank=True)

    # Security/Authentication
    last_password_update = models.DateTimeField(auto_now_add=True)
    failed_login_attempts = models.PositiveIntegerField(default=0)
    account_locked_until = models.DateTimeField(null=True, blank=True)
    two_factor_enabled = models.BooleanField(default=False)
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)

    # Audit fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "User Account"
        verbose_name_plural = "User Accounts"
        ordering = ['-date_joined']
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['phone_number']),
            models.Index(fields=['public_id']),
        ]

    def __str__(self):
        return self.get_full_name() or self.username

    def get_absolute_url(self):
        return reverse('users:profile', kwargs={'pk': self.pk})

    def requires_reconsent(self):
        return self.consent_version != settings.CURRENT_POLICY_VERSION

    def lock_account(self):
        """Lock account due to too many failed login attempts"""
        self.account_locked_until = timezone.now() + timezone.timedelta(minutes=30)
        self.save(update_fields=['account_locked_until'])
        logger.warning(f"Account locked for user {self.username}")

    def reset_login_attempts(self):
        """Reset failed login attempts counter"""
        if self.failed_login_attempts > 0:
            self.failed_login_attempts = 0
            self.save(update_fields=['failed_login_attempts'])

    def set_password(self, raw_password):
        """Override to enforce password history and policy"""
        # Validate password strength
        CustomUserManager._validate_password(None, raw_password)

        # Update password history
        PasswordHistory.objects.create(
            user=self,
            password=make_password(raw_password)
        )

        # Keep only last 5 passwords
        passwords = PasswordHistory.objects.filter(user=self).order_by('-created_at')
        if passwords.count() > 5:
            for p in passwords[5:]:
                p.delete()

        super().set_password(raw_password)
        self.last_password_update = timezone.now()
        self.save(update_fields=['last_password_update'])


class Profile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='profile'
    )
    profile_image = models.ImageField(
        upload_to='profile_pics/%Y/%m/%d/',
        blank=True,
        validators=[FileExtensionValidator(['jpg', 'jpeg', 'png'])],
        verbose_name="Profile Picture"
    )
    bio = models.TextField(blank=True, max_length=500, verbose_name="About Me")
    email_notifications = models.BooleanField(
        default=True,
        verbose_name="Email Notifications"
    )
    sms_notifications = models.BooleanField(
        default=False,
        verbose_name="SMS Notifications"
    )
    preferred_language = models.CharField(
        max_length=10,
        choices=[('en', 'English'), ('sw', 'Swahili')],
        default='en'
    )
    dark_mode = models.BooleanField(default=False)
    last_updated = models.DateTimeField(auto_now=True)
    preferences = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="User Preferences"
    )

    class Meta:
        verbose_name = "User Profile"
        verbose_name_plural = "User Profiles"

    def __str__(self):
        return f"{self.user.username}'s Profile"

    def save(self, *args, **kwargs):
        # Add automatic image resizing and optimization
        super().save(*args, **kwargs)
        if self.profile_image:
            try:
                img = Image.open(self.profile_image.path)
                if img.mode in ('RGBA', 'P'):
                    img = img.convert('RGB')

                # Resize only if larger than 300px in any dimension
                if img.height > 300 or img.width > 300:
                    output_size = (300, 300)
                    img.thumbnail(output_size, Image.LANCZOS)

                    # Save optimized image
                    img.save(self.profile_image.path, 'JPEG', quality=85, optimize=True)
            except Exception as e:
                logger.error(f"Error processing profile image: {e}")

    @property
    def notification_channels(self):
        channels = []
        if self.email_notifications:
            channels.append('email')
        if self.sms_notifications and self.user.phone_verified:
            channels.append('sms')
        return channels


class PasswordHistory(models.Model):
    """Stores password history for security compliance"""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='password_history'
    )
    password = models.CharField(max_length=128)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Password Histories"
        ordering = ['-created_at']


class Address(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='addresses'
    )
    street_address = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20)
    country = CountryField(default='KE')
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Address metadata
    address_type = models.CharField(
        max_length=20,
        choices=[('home', 'Home'), ('work', 'Work'), ('other', 'Other')],
        default='home'
    )
    notes = models.TextField(blank=True, max_length=500)

    class Meta:
        verbose_name_plural = "Addresses"
        ordering = ['-is_default', '-created_at']
        unique_together = ('user', 'street_address', 'postal_code')

    def __str__(self):
        return f"{self.street_address}, {self.city}, {self.country.name}"

    def clean(self):
        """Ensure only one default address per user"""
        if self.is_default:
            # Check if another default exists
            existing_default = Address.objects.filter(
                user=self.user,
                is_default=True
            ).exclude(pk=self.pk).exists()

            if existing_default:
                raise ValidationError(
                    _('User already has a default address'),
                    code='duplicate_default'
                )

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)


class PaymentMethod(models.Model):
    """Secure payment method storage with encryption"""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='payment_methods'
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


class ActivityLog(models.Model):
    """Tracks user activity for security auditing"""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='activities'
    )
    activity_type = models.CharField(
        max_length=50,
        choices=[
            ('login', 'Login'),
            ('password_change', 'Password Change'),
            ('profile_update', 'Profile Update'),
            ('address_add', 'Address Added'),
            ('payment_add', 'Payment Method Added'),
            ('consent_update', 'Consent Updated')
        ]
    )
    ip_address = models.GenericIPAddressField()
    user_agent = models.CharField(max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True)
    additional_info = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name_plural = "Activity Logs"
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.get_activity_type_display()} by {self.user} at {self.timestamp}"