# users/forms.py

from PIL import Image
from django_countries.widgets import CountrySelectWidget
from django import forms
from django.contrib.auth.forms import UserCreationForm, PasswordChangeForm
from django.contrib.auth.forms import PasswordChangeForm as AuthPasswordChangeForm
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from .models import Profile, Address
import requests
import re
import logging

User = get_user_model()
logger = logging.getLogger(__name__)


class UnifiedProfileForm(forms.Form):
    """
    Unified form for updating both User and Profile models.
    Handles all profile-related fields in a single, cohesive form.
    """

    # ===== USER MODEL FIELDS =====
    first_name = forms.CharField(
        max_length=150,
        required=True,
        label=_('First Name'),
        widget=forms.TextInput(attrs={
            'class': 'form-input w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition-colors',
            'placeholder': 'Enter your first name',
            'autocomplete': 'given-name',
            'x-model': 'firstName',
            '@input': 'validateName("first")'
        }),
        error_messages={
            'required': _('First name is required'),
            'max_length': _('First name cannot exceed 150 characters')
        }
    )

    last_name = forms.CharField(
        max_length=150,
        required=True,
        label=_('Last Name'),
        widget=forms.TextInput(attrs={
            'class': 'form-input w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition-colors',
            'placeholder': 'Enter your last name',
            'autocomplete': 'family-name',
            'x-model': 'lastName',
            '@input': 'validateName("last")'
        }),
        error_messages={
            'required': _('Last name is required'),
            'max_length': _('Last name cannot exceed 150 characters')
        }
    )

    phone_number = forms.CharField(
        max_length=20,
        required=False,
        label=_('Phone Number'),
        widget=forms.TextInput(attrs={
            'class': 'form-input w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition-colors',
            'placeholder': '+254712345678',
            'autocomplete': 'tel',
            'x-model': 'phoneNumber',
            '@input': 'validatePhone()',
            'pattern': r'^\+?[1-9]\d{1,14}$'
        }),
        help_text=_('International format: +254712345678')
    )

    # ===== PROFILE MODEL FIELDS =====
    profile_image = forms.ImageField(
        required=False,
        label=_('Profile Picture'),
        widget=forms.FileInput(attrs={
            'class': 'hidden',
            'accept': 'image/jpeg,image/png,image/jpg',
            'id': 'profile-image-input',
            '@change': 'handleImagePreview($event)'
        }),
        help_text=_('JPG or PNG, max 5MB')
    )

    bio = forms.CharField(
        required=False,
        label=_('Bio'),
        max_length=500,
        widget=forms.Textarea(attrs={
            'class': 'form-textarea w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition-colors resize-none',
            'placeholder': 'Tell us a bit about yourself...',
            'rows': 4,
            'maxlength': 500,
            'x-model': 'bio',
            '@input': 'updateCharCount()'
        })
    )

    date_of_birth = forms.DateField(
        required=False,
        label=_('Date of Birth'),
        widget=forms.DateInput(attrs={
            'class': 'form-input w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition-colors',
            'type': 'date',
            'max': '',  # Will be set dynamically to today's date
        })
    )

    preferred_language = forms.ChoiceField(
        required=False,
        label=_('Preferred Language'),
        choices=[],  # Will be populated in __init__
        widget=forms.Select(attrs={
            'class': 'form-select w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition-colors'
        })
    )

    # ===== BOOLEAN PREFERENCES =====
    dark_mode = forms.BooleanField(
        required=False,
        label=_('Enable Dark Mode'),
        widget=forms.CheckboxInput(attrs={
            'class': 'toggle-checkbox',
            'x-model': 'darkMode'
        })
    )

    email_notifications = forms.BooleanField(
        required=False,
        label=_('Email Notifications'),
        widget=forms.CheckboxInput(attrs={
            'class': 'toggle-checkbox',
            'x-model': 'emailNotifications'
        }),
        help_text=_('Receive order updates and important account notifications via email')
    )

    sms_notifications = forms.BooleanField(
        required=False,
        label=_('SMS Notifications'),
        widget=forms.CheckboxInput(attrs={
            'class': 'toggle-checkbox',
            'x-model': 'smsNotifications'
        }),
        help_text=_('Receive order updates via SMS (charges may apply)')
    )

    marketing_optin = forms.BooleanField(
        required=False,
        label=_('Marketing Communications'),
        widget=forms.CheckboxInput(attrs={
            'class': 'toggle-checkbox',
            'x-model': 'marketingOptin'
        }),
        help_text=_('Receive promotional emails about new products and special offers')
    )

    def __init__(self, *args, user=None, **kwargs):
        """
        Initialize form with user context and populate initial values.
        """
        self.user = user
        super().__init__(*args, **kwargs)

        # Set language choices from settings
        from django.conf import settings
        self.fields['preferred_language'].choices = settings.LANGUAGES

        # Populate initial values if user exists
        if self.user:
            profile = getattr(self.user, 'profile', None)

            # User fields
            self.initial['first_name'] = self.user.first_name
            self.initial['last_name'] = self.user.last_name
            self.initial['phone_number'] = self.user.phone_number

            # Profile fields
            if profile:
                self.initial['bio'] = profile.bio
                self.initial['date_of_birth'] = profile.date_of_birth
                self.initial['preferred_language'] = profile.preferred_language
                self.initial['dark_mode'] = profile.dark_mode
                self.initial['email_notifications'] = profile.email_notifications
                self.initial['sms_notifications'] = profile.sms_notifications
                self.initial['marketing_optin'] = profile.marketing_optin

        # Store original phone number for change detection
        self.original_phone = self.user.phone_number if self.user else None

    def clean_first_name(self):
        """Validate first name contains only letters and basic punctuation."""
        first_name = self.cleaned_data.get('first_name', '').strip()

        if not first_name:
            raise ValidationError(_('First name cannot be empty'))

        # Allow letters, spaces, hyphens, apostrophes (for names like O'Brien, Mary-Jane)
        if not re.match(r"^[a-zA-Z\s\-']+$", first_name):
            raise ValidationError(
                _('First name can only contain letters, spaces, hyphens, and apostrophes')
            )

        # Check for reasonable length
        if len(first_name) < 2:
            raise ValidationError(_('First name must be at least 2 characters long'))

        return first_name

    def clean_last_name(self):
        """Validate last name contains only letters and basic punctuation."""
        last_name = self.cleaned_data.get('last_name', '').strip()

        if not last_name:
            raise ValidationError(_('Last name cannot be empty'))

        if not re.match(r"^[a-zA-Z\s\-']+$", last_name):
            raise ValidationError(
                _('Last name can only contain letters, spaces, hyphens, and apostrophes')
            )

        if len(last_name) < 2:
            raise ValidationError(_('Last name must be at least 2 characters long'))

        return last_name

    def clean_phone_number(self):
        """
        Validate phone number in E.164 format.
        Check for duplicates (excluding current user).
        """
        phone = self.cleaned_data.get('phone_number', '').strip()

        if not phone:
            return phone

        # Remove spaces and dashes for validation
        phone_clean = phone.replace(' ', '').replace('-', '')

        # E.164 format validation: +[country code][number]
        # Must start with + and have 10-15 digits total
        e164_pattern = r'^\+[1-9]\d{9,14}$'

        if not re.match(e164_pattern, phone_clean):
            raise ValidationError(
                _('Phone number must be in international format: +254712345678 (E.164 standard)')
            )

        # Check for duplicate phone numbers (exclude current user)
        if self.user:
            duplicate = User.objects.filter(
                phone_number=phone_clean
            ).exclude(pk=self.user.pk).exists()

            if duplicate:
                raise ValidationError(
                    _('This phone number is already registered to another account')
                )

        return phone_clean

    def clean_date_of_birth(self):
        """Validate date of birth is not in the future and user is at least 13 years old."""
        dob = self.cleaned_data.get('date_of_birth')

        if not dob:
            return dob

        from datetime import date, timedelta
        today = date.today()

        # Check if date is in the future
        if dob > today:
            raise ValidationError(_('Date of birth cannot be in the future'))

        # Check minimum age (13 years for COPPA compliance)
        min_age_date = today - timedelta(days=13 * 365.25)
        if dob > min_age_date:
            raise ValidationError(_('You must be at least 13 years old to use this service'))

        # Check maximum age (reasonable limit: 120 years)
        max_age_date = today - timedelta(days=120 * 365.25)
        if dob < max_age_date:
            raise ValidationError(_('Please enter a valid date of birth'))

        return dob

    def clean_profile_image(self):
        """
        Validate profile image:
        - File type (JPEG, PNG only)
        - File size (max 5MB)
        - Image dimensions (reasonable limits)
        """
        image = self.cleaned_data.get('profile_image')

        if not image:
            return image

        # Check file size (5MB limit)
        max_size = 5 * 1024 * 1024  # 5MB in bytes
        if image.size > max_size:
            raise ValidationError(
                _('Image file size cannot exceed 5MB. Current size: %(size).1fMB') % {
                    'size': image.size / (1024 * 1024)
                }
            )

        # Check file type
        allowed_types = ['image/jpeg', 'image/jpg', 'image/png']
        if image.content_type not in allowed_types:
            raise ValidationError(
                _('Only JPEG and PNG images are allowed')
            )

        # Validate actual image (not just extension)
        try:
            img = Image.open(image)
            img.verify()

            # Check image dimensions (reasonable limits)
            # Reset file pointer after verify()
            image.seek(0)
            img = Image.open(image)

            width, height = img.size

            # Maximum dimension: 4096px
            if width > 4096 or height > 4096:
                raise ValidationError(
                    _('Image dimensions cannot exceed 4096x4096 pixels')
                )

            # Minimum dimension: 100px
            if width < 100 or height < 100:
                raise ValidationError(
                    _('Image must be at least 100x100 pixels')
                )

        except Exception as e:
            logger.error(f"Image validation error: {str(e)}")
            raise ValidationError(
                _('Invalid image file. Please upload a valid JPEG or PNG image')
            )

        return image

    def clean_bio(self):
        """Clean and validate bio text."""
        bio = self.cleaned_data.get('bio', '').strip()

        # Remove excessive whitespace
        bio = re.sub(r'\s+', ' ', bio)

        # Check length
        if len(bio) > 500:
            raise ValidationError(
                _('Bio cannot exceed 500 characters')
            )

        return bio

    def has_phone_changed(self):
        """Check if phone number has been modified."""
        new_phone = self.cleaned_data.get('phone_number', '').strip()
        return self.original_phone != new_phone and new_phone != ''

    def get_changed_fields(self):
        """
        Return dictionary of changed fields with old and new values.
        Useful for activity logging.

        Serializes values to JSON-compatible formats (converts dates to ISO strings).
        """
        if not self.user:
            return {}

        changes = {}
        profile = getattr(self.user, 'profile', None)

        # Helper function to serialize values for JSON
        def serialize_value(value):
            """Convert value to JSON-serializable format"""
            if value is None:
                return None
            # Convert date/datetime to ISO format string
            if hasattr(value, 'isoformat'):
                return value.isoformat()
            # Convert other objects to string
            return str(value)

        # Check user fields
        user_fields = {
            'first_name': self.user.first_name,
            'last_name': self.user.last_name,
            'phone_number': self.user.phone_number
        }

        for field, old_value in user_fields.items():
            new_value = self.cleaned_data.get(field)
            if str(old_value) != str(new_value):
                changes[field] = {
                    'old': serialize_value(old_value),
                    'new': serialize_value(new_value)
                }

        # Check profile fields
        if profile:
            profile_fields = {
                'bio': profile.bio,
                'date_of_birth': profile.date_of_birth,
                'preferred_language': profile.preferred_language,
                'dark_mode': profile.dark_mode,
                'email_notifications': profile.email_notifications,
                'sms_notifications': profile.sms_notifications,
                'marketing_optin': profile.marketing_optin
            }

            for field, old_value in profile_fields.items():
                new_value = self.cleaned_data.get(field)
                if str(old_value) != str(new_value):
                    changes[field] = {
                        'old': serialize_value(old_value),
                        'new': serialize_value(new_value)
                    }

        return changes

    def save(self, commit=True):
        """
        Save form data to both User and Profile models.
        Returns tuple: (user, profile, changed_fields)
        """
        if not self.user:
            raise ValueError("User must be provided to save the form")

        # Track changes
        changed_fields = self.get_changed_fields()

        # Update User model fields
        self.user.first_name = self.cleaned_data['first_name']
        self.user.last_name = self.cleaned_data['last_name']
        self.user.phone_number = self.cleaned_data.get('phone_number', '')

        if commit:
            self.user.save(update_fields=['first_name', 'last_name', 'phone_number'])

        # Get or create profile
        profile, created = Profile.objects.get_or_create(user=self.user)

        # Update Profile model fields
        profile.bio = self.cleaned_data.get('bio', '')
        profile.date_of_birth = self.cleaned_data.get('date_of_birth')
        profile.preferred_language = self.cleaned_data.get('preferred_language', 'en')
        profile.dark_mode = self.cleaned_data.get('dark_mode', False)
        profile.email_notifications = self.cleaned_data.get('email_notifications', True)
        profile.sms_notifications = self.cleaned_data.get('sms_notifications', False)
        profile.marketing_optin = self.cleaned_data.get('marketing_optin', False)

        # Handle profile image separately (don't override if not uploaded)
        if self.cleaned_data.get('profile_image'):
            # Delete old image if exists
            if profile.profile_image:
                try:
                    profile.profile_image.delete(save=False)
                except Exception as e:
                    logger.warning(f"Could not delete old profile image: {e}")

            profile.profile_image = self.cleaned_data['profile_image']

        if commit:
            profile.save()

        return self.user, profile, changed_fields

def _validate_recaptcha(token):
    """Validate reCAPTCHA token with Google API"""
    if settings.DEBUG:
        logger.debug("Skipping reCAPTCHA validation in development mode")
        return True

    if not token:
        logger.warning("Missing reCAPTCHA token")
        return False

    try:
        response = requests.post(
            'https://www.google.com/recaptcha/api/siteverify',
            data={
                'secret': settings.RECAPTCHA_SECRET_KEY,
                'response': token
            },
            timeout=3
        )
        response.raise_for_status()
        result = response.json()

        if not result.get('success'):
            logger.error(f"reCAPTCHA validation failed: {result}")
            return False

        return True
    except requests.RequestException as e:
        logger.error(f"reCAPTCHA validation request failed: {str(e)}")
        return False


class UserRegisterForm(UserCreationForm):
    # Only essential fields
    first_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Your first name',
            'aria-label': 'First name'
        })
    )

    last_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Your last name',
            'aria-label': 'Last name'
        })
    )

    # Privacy and marketing fields
    accept_terms = forms.BooleanField(
        required=True,
        label=mark_safe(
            'I agree to the <a href="/legal/terms/" target="_blank" rel="noopener noreferrer">Terms of Service</a>'),
        error_messages={'required': _('You must accept the Terms of Service')}
    )

    marketing_optin = forms.BooleanField(
        required=False,
        label='I want to receive marketing communications',
        widget=forms.CheckboxInput(attrs={
            'aria-label': 'Marketing communications opt-in'
        })
    )

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'password1', 'password2']
        widgets = {
            'email': forms.EmailInput(attrs={
                'autocomplete': 'email',
                'aria-label': 'Email address',
                'placeholder': 'your@email.com'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].help_text = self.password_help_text()

        # Add consistent CSS classes
        for field_name in self.fields:
            if field_name not in ['accept_terms', 'marketing_optin']:
                self.fields[field_name].widget.attrs.update({'class': 'form-control'})

        # Add reCAPTCHA if configured
        if getattr(settings, "RECAPTCHA_SITE_KEY", None):
            self.fields['recaptcha'] = forms.CharField(
                widget=forms.HiddenInput(),
                required=False
            )

    def password_help_text(self):
        return mark_safe('''
        <div class="form-text text-muted mt-2">
            Password must contain:
            <ul class="mb-0">
                <li class="req-length">At least 10 characters</li>
                <li class="req-upper">One uppercase letter</li>
                <li class="req-lower">One lowercase letter</li>
                <li class="req-digit">One digit</li>
                <li class="req-special">One special character</li>
            </ul>
        </div>
        ''')

    def clean(self):
        cleaned_data = super().clean()

        # Password mismatch fallback (for tests and safety)
        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            self.add_error('password2', ValidationError(_("Passwords don't match"), code='password_mismatch'))

        # reCAPTCHA validation
        if getattr(settings, "RECAPTCHA_SITE_KEY", None):
            recaptcha_token = cleaned_data.get('recaptcha')
            if not _validate_recaptcha(recaptcha_token):
                self.add_error(None, ValidationError(
                    _("reCAPTCHA validation failed. Please try again."),
                    code='recaptcha_failed'
                ))

        return cleaned_data

    def clean_email(self):
        email = self.cleaned_data['email'].lower().strip()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError(
                _("An account with this email already exists."),
                code='duplicate_email'
            )
        return email

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")

        if not password1:
            raise ValidationError(_("Please enter your password."), code='password_missing')

        if password1 and password2 and password1 != password2:
            raise ValidationError(_("Passwords don't match"), code='password_mismatch')

        # Custom password validation
        if len(password1) < 10:
            raise ValidationError(_("Password must be at least 10 characters long."), code='password_too_short')

        if not re.search(r'[A-Z]', password1):
            raise ValidationError(_("Password must contain at least one uppercase letter."), code='password_no_upper')

        if not re.search(r'[a-z]', password1):
            raise ValidationError(_("Password must contain at least one lowercase letter."), code='password_no_lower')

        if not re.search(r'[0-9]', password1):
            raise ValidationError(_("Password must contain at least one digit."), code='password_no_digit')

        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password1):
            raise ValidationError(_("Password must contain at least one special character."), code='password_no_special')

        # Check against common passwords
        common_passwords = ['password', '12345678', 'qwertyui', 'kenya123', 'nairobi']
        if password1.lower() in common_passwords:
            raise ValidationError(_("This password is too common and insecure."), code='password_common')

        return password2

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = self.cleaned_data['email'].lower().strip()
        user.email = self.cleaned_data['email'].lower().strip()

        if commit:
            user.save()
        return user



class ProfileUpdateForm(forms.ModelForm):
    email = forms.EmailField(
        disabled=True,  # read-only
        help_text="Contact support to change email",
        widget=forms.EmailInput(attrs={'aria-label': 'Email (read-only)'})
    )

    class Meta:
        model = Profile
        fields = [
            'profile_image',
            'email_notifications',
            'sms_notifications',
            'preferred_language',
            'dark_mode',
            'date_of_birth'   # added date_of_birth if you want to render it
        ]
        widgets = {
            'profile_image': forms.FileInput(attrs={
                'accept': 'image/*',
                'id': 'profileImageUpload',
            }),
            'preferred_language': forms.Select(attrs={
                'class': 'form-select-lg',
                'aria-label': 'Preferred language'
            }),
            # add widget settings for 'date_of_birth' if needed
            'date_of_birth': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
                'aria-label': 'Date of birth'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['email'].initial = self.instance.user.email



class UserProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'phone_number', 'email']  # added 'email'
        widgets = {
            'first_name': forms.TextInput(attrs={
                'class': 'form-control',
                'aria-label': 'First name'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'form-control',
                'aria-label': 'Last name'
            }),
            'phone_number': forms.TextInput(attrs={
                'class': 'form-control',
                'data-mask': '+254000000000',
                'aria-label': 'Phone number'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'aria-label': 'Email address'
            }),
        }

    def clean_phone_number(self):
        phone_number = self.cleaned_data.get('phone_number')
        phone_regex = r'^\+?1?\d{9,15}$'
        if phone_number and not re.match(phone_regex, phone_number):
            raise ValidationError(
                _("Phone number must be in international format: '+999999999'"),
                code='invalid_phone'
            )
        return phone_number


class AddressForm(forms.ModelForm):
    """Form for creating and updating user addresses."""

    class Meta:
        model = Address
        fields = [
            'nickname',
            'address_type',
            'full_name',
            'street_address',
            'city',
            'state',
            'postal_code',
            'country',
            'phone',
            'is_default',
        ]

        widgets = {
            'nickname': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Home, Office',
            }),
            'address_type': forms.Select(attrs={
                'class': 'form-select',
            }),
            'full_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'John Doe',
            }),
            'street_address': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '123 Main Street, Apt 4B',
            }),
            'city': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nairobi',
            }),
            'state': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nairobi County',
            }),
            'postal_code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '00100',
            }),
            'country': CountrySelectWidget(attrs={
                'class': 'form-select',
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '+254712345678',
            }),
            'is_default': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
            }),
        }

    def __init__(self, *args, user=None, **kwargs):
        """Initialize form with user context."""
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_nickname(self):
        """Validate nickname uniqueness for the user."""
        nickname = self.cleaned_data.get('nickname', '').strip()

        if not nickname:
            return nickname

        # Check if nickname already exists for this user (excluding current instance)
        queryset = Address.objects.filter(
            user=self.user,
            nickname__iexact=nickname
        )

        # Exclude current instance when editing
        if self.instance and self.instance.pk:
            queryset = queryset.exclude(pk=self.instance.pk)

        if queryset.exists():
            raise forms.ValidationError(
                f'You already have an address with the nickname "{nickname}". '
                'Please choose a different name.'
            )

        return nickname

    def clean_phone(self):
        """Validate and normalize phone number."""
        phone = self.cleaned_data.get('phone', '').strip()

        if not phone:
            return phone

        phone_digits = phone.replace(' ', '').replace('-', '')

        if not phone_digits.startswith('+'):
            raise forms.ValidationError(
                "Phone number must start with country code (e.g., +254712345678)"
            )

        if len(phone_digits) < 10 or len(phone_digits) > 17:
            raise forms.ValidationError(
                "Phone number must be between 9 and 16 digits (plus country code)"
            )

        return phone_digits

    def save(self, commit=True):
        """Save address with proper default handling."""
        address = super().save(commit=False)

        # If this address is being set as default, unset other defaults
        if address.is_default and self.user:
            Address.objects.filter(user=self.user).update(is_default=False)

        if commit:
            address.save()

        return address

class PasswordUpdateForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs.update({
                'class': 'form-control',
                'autocomplete': 'new-password',
                'aria-label': field.label
            })


class PasswordChangeForm(AuthPasswordChangeForm):
    def clean_new_password1(self):
        password = self.cleaned_data.get('new_password1')
        # Your custom validation
        errors = []
        if len(password) < 10:
            errors.append("Password must be at least 10 characters long")
        if not re.search(r'[A-Z]', password):
            errors.append("Password must contain at least one uppercase letter")
        if not re.search(r'[a-z]', password):
            errors.append("Password must contain at least one lowercase letter")
        if not re.search(r'[0-9]', password):
            errors.append("Password must contain at least one digit")
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            errors.append("Password must contain at least one special character")
        if errors:
            raise ValidationError(errors)
        return password


class TwoFactorSetupForm(forms.Form):
    METHOD_CHOICES = [
        ('email', 'Email Verification'),
        ('sms', 'SMS Verification'),
        ('authenticator', 'Authenticator App')
    ]

    method = forms.ChoiceField(
        choices=METHOD_CHOICES,
        widget=forms.RadioSelect,
        initial='email',
        label=_('Two-factor authentication method'),
        help_text=_('Choose how you want to receive verification codes')
    )

    phone_number = forms.CharField(
        required=False,
        label=_('Phone number for SMS verification'),
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '+2547XXXXXXXX',
            'data-mask': '+254000000000',
            'aria-label': 'Phone number for SMS'
        })
    )

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        if not user.phone_verified:
            # Remove SMS option if phone not verified
            self.fields['method'].choices = [
                ('email', 'Email Verification'),
                ('authenticator', 'Authenticator App')
            ]
            del self.fields['phone_number']
        else:
            # Pre-populate phone number
            self.fields['phone_number'].initial = user.phone_number

    def clean(self):
        cleaned_data = super().clean()
        method = cleaned_data.get('method')
        if method == 'sms':
            phone_number = cleaned_data.get('phone_number')
            if not phone_number:
                self.add_error('phone_number', ValidationError(
                    _("Phone number is required for SMS verification"),
                    code='phone_required'
                ))
            elif not re.match(r'^\+?254\d{9}$', phone_number):
                self.add_error('phone_number', ValidationError(
                    _("Phone number must be in the format: '+2547XXXXXXXX'"),
                    code='invalid_phone'
                ))
        return cleaned_data


class ConsentUpdateForm(forms.Form):
    terms_accepted = forms.BooleanField(
        required=True,
        label=_('I agree to the updated Terms of Service'),
        widget=forms.CheckboxInput(attrs={
            'aria-label': 'Accept updated Terms of Service'
        })
    )
    privacy_accepted = forms.BooleanField(
        required=True,
        label=_('I agree to the updated Privacy Policy'),
        widget=forms.CheckboxInput(attrs={
            'aria-label': 'Accept updated Privacy Policy'
        })
    )


class AccountDeletionForm(forms.Form):
    confirm = forms.BooleanField(
        required=True,
        label=_('I understand this action is permanent and cannot be undone'),
        widget=forms.CheckboxInput(attrs={'aria-label': 'Confirm account deletion'})
    )

    password = forms.CharField(
        label=_('Your Password'),
        widget=forms.PasswordInput(attrs={
            'autocomplete': 'current-password',
            'aria-label': 'Enter password to confirm deletion'
        }),
        strip=False,
    )

    # Fix: Make user parameter optional in initialization
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

    def clean_password(self):
        password = self.cleaned_data.get('password')
        if not self.user or not self.user.check_password(password):
            raise ValidationError(_('Your password was entered incorrectly'))
        return password