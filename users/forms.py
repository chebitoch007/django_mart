# users/forms.py

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