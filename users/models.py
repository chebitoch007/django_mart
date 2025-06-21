from django.contrib.auth.models import AbstractUser, BaseUserManager
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


class EncryptionManager:
    """Handles encryption/decryption of sensitive fields"""

    def __init__(self):
        self.cipher = Fernet(settings.FIELD_ENCRYPTION_KEY)

    def encrypt(self, value):
        return self.cipher.encrypt(value.encode()).decode()

    def decrypt(self, encrypted_value):
        return self.cipher.decrypt(encrypted_value.encode()).decode()


class CustomUserManager(BaseUserManager):
    """Custom manager with security methods"""
    use_in_migrations = True

    def _create_user(self, username, email, password, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(username=username, email=email, **extra_fields)

        # Validate and set password
        if password:
            self._validate_password(password)
            user.set_password(password)
        else:
            user.set_unusable_password()

        user.save(using=self._db)
        return user

    def create_user(self, username, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        return self._create_user(username, email, password, **extra_fields)

    def create_superuser(self, username, email, password, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self._create_user(username, email, password, **extra_fields)

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

    def get_by_natural_key(self, username):
        # Handle both email and username
        return self.get(
            models.Q(**{self.model.USERNAME_FIELD: username}) |
            models.Q(email__iexact=username)
        )

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

    registration_street_address = models.CharField(
        _('registration street address'),
        max_length=255,
        blank=True,
        null=True
    )
    registration_city = models.CharField(
        _('registration city'),
        max_length=100,
        blank=True,
        null=True
    )
    registration_state = models.CharField(
        _('registration state/province'),
        max_length=100,
        blank=True,
        null=True
    )
    registration_postal_code = models.CharField(
        _('registration postal code'),
        max_length=20,
        blank=True,
        null=True
    )

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

        # Call super to set the password first
        super().set_password(raw_password)
        self.last_password_update = timezone.now()

        # Only create PasswordHistory if user is already saved
        if self.pk:
            PasswordHistory.objects.create(
                user=self,
                password=make_password(raw_password)
            )

            # Keep only last 5 passwords
            passwords = PasswordHistory.objects.filter(user=self).order_by('-created_at')
            if passwords.count() > 5:
                for p in passwords[5:]:
                    p.delete()

            # Save user after updating password history
            self.save(update_fields=['last_password_update'])


class Profile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='profile'
    )

    profile_image = models.ImageField(
        _('profile picture'),
        upload_to='profile_pics/',
        blank=True,
        null=True
    )
    bio = models.TextField(_('bio'), blank=True)
    email_notifications = models.BooleanField(_('email notifications'), default=True)
    sms_notifications = models.BooleanField(_('SMS notifications'), default=False)
    preferred_language = models.CharField(
        _('preferred language'),
        max_length=10,
        choices=settings.LANGUAGES,
        default=settings.LANGUAGE_CODE
    )
    dark_mode = models.BooleanField(_('dark mode'), default=False)
    two_factor_enabled = models.BooleanField(_('two factor authentication'), default=False)
    last_updated = models.DateTimeField(_('last updated'), auto_now=True)

    class Meta:
        verbose_name = _('profile')
        verbose_name_plural = _('profiles')

    def __str__(self):
        return f"{self.user.username}'s Profile"


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
    ADDRESS_TYPES = (
        ('home', 'Home'),
        ('work', 'Work'),
        ('other', 'Other'),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='addresses'
    )
    nickname = models.CharField(_('nickname'), max_length=50, blank=True)
    address_type = models.CharField(
        _('address type'),
        max_length=10,
        choices=ADDRESS_TYPES,
        default='home'
    )
    full_name = models.CharField(_('full name'), max_length=100)
    street_address = models.CharField(_('street address'), max_length=255)
    city = models.CharField(_('city'), max_length=100)
    state = models.CharField(_('state/province'), max_length=100)
    postal_code = models.CharField(_('postal code'), max_length=20)
    country = models.CharField(_('country'), max_length=50, default='Kenya')
    phone = models.CharField(
        _('phone number'),
        max_length=17,
        validators=[CustomUser.phone_regex],
        blank=True
    )
    is_default = models.BooleanField(_('default address'), default=False)
    created = models.DateTimeField(_('created at'), auto_now_add=True)
    updated = models.DateTimeField(_('updated at'), auto_now=True)

    class Meta:
        verbose_name = _('address')
        verbose_name_plural = _('addresses')
        ordering = ['-is_default', '-created']
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'nickname'],
                name='unique_address_nickname'
            )
        ]

    def __str__(self):
        return f"{self.full_name}, {self.street_address}, {self.city}"


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