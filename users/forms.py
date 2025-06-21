import requests
from django.contrib.auth.forms import UserCreationForm, PasswordChangeForm
from django import forms
from django.utils.safestring import mark_safe
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from .models import Profile, Address
import re
import logging

User = get_user_model()
logger = logging.getLogger(__name__)


# Helper functions
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
            timeout=3  # Add timeout to prevent hanging
        )
        response.raise_for_status()
        result = response.json()
        return result.get('success', False)
    except requests.RequestException as e:
        logger.error(f"reCAPTCHA validation failed: {str(e)}")
        return False


def luhn_checksum(card_number):
    """Validate card number using Luhn algorithm"""

    def digits_of(n):
        return [int(d) for d in str(n)]

    digits = digits_of(card_number)
    odd_digits = digits[-1::-2]
    even_digits = digits[-2::-2]
    total = sum(odd_digits)
    for d in even_digits:
        total += sum(digits_of(d * 2))
    return total % 10 == 0


class UserRegisterForm(UserCreationForm):
    street_address = forms.CharField(
        max_length=255,
        required=True,
        label=_('Street Address'),
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '123 Main Street',
            'aria-label': 'Street address'
        })
    )
    city = forms.CharField(
        max_length=100,
        required=True,
        label=_('City'),
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g. Nairobi',
            'aria-label': 'City'
        })
    )
    state = forms.CharField(
        max_length=100,
        required=True,
        label=_('State/Province'),
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g. Nairobi County',
            'aria-label': 'State'
        })
    )
    postal_code = forms.CharField(
        max_length=20,
        required=True,
        label=_('Postal Code'),
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Postal code',
            'aria-label': 'Postal code'
        })
    )

    accept_terms = forms.BooleanField(
        required=True,
        label=mark_safe(
            'I agree to the <a href="/legal/terms/" target="_blank" rel="noopener noreferrer">Terms of Service</a>'),
        error_messages={'required': _('You must accept the Terms of Service')}
    )

    accept_privacy = forms.BooleanField(
        required=True,
        label=mark_safe(
            'I agree to the <a href="/legal/privacy/" target="_blank" rel="noopener noreferrer">Privacy Policy</a>'),
        error_messages={'required': _('You must accept the Privacy Policy')}
    )

    phone_number = forms.CharField(
        max_length=20,
        required=True,
        help_text="Format: +2547XXXXXXXX",
        widget=forms.TextInput(attrs={
            'placeholder': '+2547XXXXXXXX',
            'data-mask': '+254000000000'
        })
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'phone_number', 'password1', 'password2',
                  'street_address', 'city', 'state', 'postal_code']
        help_texts = {'username': None}
        widgets = {
            'username': forms.TextInput(attrs={
                'autocomplete': 'username',
                'aria-label': 'Username'
            }),
            'email': forms.EmailInput(attrs={
                'autocomplete': 'email',
                'aria-label': 'Email address'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Password strength help text
        password_help = '''
        <div class="form-text text-muted">
            Password must contain:
            <ul class="mb-0">
                <li class="req-length">At least 10 characters</li>
                <li class="req-upper">One uppercase letter</li>
                <li class="req-lower">One lowercase letter</li>
                <li class="req-digit">One digit</li>
                <li class="req-special">One special character</li>
            </ul>
        </div>
        '''

        self.fields['password1'].help_text = mark_safe(password_help)

        # Add Bootstrap classes and placeholders
        for field_name, field in self.fields.items():
            if field_name not in ['accept_terms', 'accept_privacy']:
                field.widget.attrs.update({'class': 'form-control-lg'})

            # Add aria-labels for accessibility
            if not field.widget.attrs.get('aria-label'):
                field.widget.attrs['aria-label'] = field.label or field_name.replace('_', ' ')

        self.fields['username'].widget.attrs['placeholder'] = 'Choose a username'
        self.fields['email'].widget.attrs['placeholder'] = 'Your email address'
        self.fields['phone_number'].widget.attrs['placeholder'] = '+2547XXXXXXXX'

        # Add reCAPTCHA if configured
        if settings.RECAPTCHA_SITE_KEY:
            self.fields['recaptcha'] = forms.CharField(
                widget=forms.HiddenInput(),
                required=False
            )

    def clean(self):
        cleaned_data = super().clean()
        if settings.RECAPTCHA_SITE_KEY:
            recaptcha_token = cleaned_data.get('recaptcha')
            if not _validate_recaptcha(recaptcha_token):
                self.add_error(None, ValidationError(
                    _("reCAPTCHA validation failed. Please try again."),
                    code='recaptcha_failed'
                ))
        return cleaned_data

    def clean_phone_number(self):
        phone_number = self.cleaned_data['phone_number']
        pattern = r'^\+?254\d{9}$'
        if not re.match(pattern, phone_number):
            raise ValidationError(
                _("Phone number must be in the format: '+2547XXXXXXXX'"),
                code='invalid_phone'
            )
        return phone_number

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

        if password1 and password2 and password1 != password2:
            raise ValidationError(
                _("Passwords don't match"),
                code='password_mismatch'
            )

        # Custom password validation
        if len(password1) < 10:
            raise ValidationError(
                _("Password must be at least 10 characters long."),
                code='password_too_short'
            )

        if not re.search(r'[A-Z]', password1):
            raise ValidationError(
                _("Password must contain at least one uppercase letter."),
                code='password_no_upper'
            )

        if not re.search(r'[a-z]', password1):
            raise ValidationError(
                _("Password must contain at least one lowercase letter."),
                code='password_no_lower'
            )

        if not re.search(r'[0-9]', password1):
            raise ValidationError(
                _("Password must contain at least one digit."),
                code='password_no_digit'
            )

        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password1):
            raise ValidationError(
                _("Password must contain at least one special character."),
                code='password_no_special'
            )

        # Check against common passwords
        common_passwords = [
            'password', '12345678', 'qwertyui', 'kenya123', 'nairobi'
        ]
        if password1.lower() in common_passwords:
            raise ValidationError(
                _("This password is too common and insecure."),
                code='password_common'
            )

        return password2


class ProfileUpdateForm(forms.ModelForm):
    email = forms.EmailField(
        disabled=False,
        help_text="Contact support to change email",
        widget=forms.EmailInput(attrs={'aria-label': 'Email (read-only)'})
    )

    class Meta:
        model = Profile
        fields = ['profile_image', 'email_notifications',
                  'sms_notifications', 'preferred_language', 'dark_mode']
        widgets = {
            'profile_image': forms.FileInput(attrs={
                'accept': 'image/*',
                'class': 'form-control-lg',
                'aria-label': 'Profile image'
            }),
            'bio': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': 'Tell us about yourself...',
                'aria-label': 'About me'
            }),
            'preferred_language': forms.Select(attrs={
                'class': 'form-select-lg',
                'aria-label': 'Preferred language'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['email'].initial = self.instance.user.email


class NotificationPreferencesForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['email_notifications', 'sms_notifications']
        labels = {
            'email_notifications': _('Email notifications'),
            'sms_notifications': _('SMS notifications'),
        }
        help_texts = {
            'sms_notifications': _('Requires a verified phone number'),
        }
        widgets = {
            'email_notifications': forms.CheckboxInput(attrs={
                'aria-label': 'Email notifications'
            }),
            'sms_notifications': forms.CheckboxInput(attrs={
                'aria-label': 'SMS notifications'
            }),
        }

class UserProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'phone_number', 'registration_street_address',
                  'registration_city', 'registration_state', 'registration_postal_code']
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
            'registration_street_address': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '123 Main Street',
                'aria-label': 'Street address'
            }),
            'registration_city': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. Nairobi',
                'aria-label': 'City'
            }),
            'registration_state': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. Nairobi County',
                'aria-label': 'State'
            }),
            'registration_postal_code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Postal code',
                'aria-label': 'Postal code'
            }),
        }

        def clean_phone_number(self):
            phone_number = self.cleaned_data['phone_number']
            if phone_number and not re.match(r'^\+?254\d{9}$', phone_number):
                raise ValidationError(
                    _("Phone number must be in the format: '+2547XXXXXXXX'"),
                    code='invalid_phone'
                )
            return phone_number




class AddressForm(forms.ModelForm):
    class Meta:
        model = Address
        fields = ['nickname', 'address_type', 'full_name', 'street_address',
                  'city', 'state', 'postal_code', 'country', 'phone', 'is_default']
        widgets = {
            'nickname': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Home, Work, etc.',
                'aria-label': 'Address nickname'
            }),
            'address_type': forms.Select(attrs={
                'class': 'form-select',
                'aria-label': 'Address type'
            }),
            'full_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Full Name',
                'aria-label': 'Full name'
            }),
            'street_address': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '123 Main Street',
                'aria-label': 'Street address'
            }),
            'city': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. Nairobi',
                'aria-label': 'City'
            }),
            'state': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. Nairobi County',
                'aria-label': 'State'
            }),
            'postal_code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Postal code',
                'aria-label': 'Postal code'
            }),
            'country': forms.Select(attrs={
                'class': 'form-select',
                'aria-label': 'Country'
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '+2547XXXXXXXX',
                'data-mask': '+254000000000',
                'aria-label': 'Phone number'
            }),
            'is_default': forms.CheckboxInput(attrs={
                'aria-label': 'Set as default shipping address'
            }),
        }
        labels = {
            'is_default': _('Set as default shipping address'),
        }



class PasswordUpdateForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs.update({
                'class': 'form-control',
                'autocomplete': 'new-password',
                'aria-label': field.label
            })


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


