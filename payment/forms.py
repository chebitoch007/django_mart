from django import forms
from django.conf import settings
from django.core.validators import RegexValidator

from django import forms
from .models import PaymentMethod, logger
from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
import re
import datetime


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


class PaymentMethodForm(forms.ModelForm):
    # Never store CVV long-term - this is for temporary processing only
    cvv = forms.CharField(
        max_length=4,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '***',
            'maxlength': '4',
            'autocomplete': 'off',
            'aria-label': 'CVV security code'
        })
    )

    class Meta:
        model = PaymentMethod
        fields = ['card_type', 'cardholder_name', 'is_default']
        widgets = {
            'card_type': forms.Select(attrs={
                'class': 'form-select',
                'aria-label': 'Card type'
            }),
            'cardholder_name': forms.TextInput(attrs={
                'class': 'form-control',
                'aria-label': 'Cardholder name'
            }),
            'is_default': forms.CheckboxInput(attrs={
                'aria-label': 'Set as default payment method'
            }),
        }
        labels = {
            'is_default': _('Set as default payment method'),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['card_number'] = forms.CharField(
            max_length=19,
            required=True,
            widget=forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '**** **** **** ****',
                'data-mask': '0000 0000 0000 0000',
                'aria-label': 'Card number'
            })
        )
        self.fields['expiry_date'] = forms.CharField(
            max_length=7,
            required=True,
            widget=forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'MM/YYYY',
                'data-mask': '00/0000',
                'aria-label': 'Expiry date'
            })
        )

        # Set initial values if editing
        if self.instance.pk:
            self.fields['card_number'].initial = self.instance.get_decrypted_card_number()
            self.fields['expiry_date'].initial = self.instance.get_decrypted_expiry_date()

    def clean_card_number(self):
        card_number = self.cleaned_data['card_number'].replace(' ', '')
        if not card_number.isdigit() or len(card_number) < 13 or len(card_number) > 19:
            raise ValidationError(
                _("Please enter a valid card number"),
                code='invalid_card'
            )

        # Validate with Luhn algorithm in production
        if not settings.DEBUG and not luhn_checksum(card_number):
            raise ValidationError(
                _("Invalid card number"),
                code='invalid_card'
            )

        return card_number

    def clean_expiry_date(self):
        expiry_date = self.cleaned_data['expiry_date']
        try:
            if '/' in expiry_date:
                month, year = map(int, expiry_date.split('/'))
            else:
                # Handle formats without separator
                if len(expiry_date) < 4:
                    raise ValidationError(_("Invalid expiration date format"))
                month = int(expiry_date[:2])
                year = int(expiry_date[2:])

            if month < 1 or month > 12:
                raise ValueError

            # Handle two-digit year input
            if year < 100:
                current_year = datetime.date.today().year
                century = current_year // 100 * 100
                year += century
                if year < current_year:
                    year += 100

            # Validate expiration date
            current_date = datetime.date.today()
            if year < current_date.year or (year == current_date.year and month < current_date.month):
                raise ValidationError(
                    _("This card has expired"),
                    code='card_expired'
                )

            return f"{month:02d}/{year}"

        except (ValueError, IndexError):
            raise ValidationError(
                _("Please enter a valid expiration date in MM/YYYY format"),
                code='invalid_expiry'
            )

    def clean_cvv(self):
        cvv = self.cleaned_data['cvv']
        if not cvv.isdigit() or len(cvv) not in (3, 4):
            raise ValidationError(
                _("Please enter a valid CVV"),
                code='invalid_cvv'
            )
        return cvv

    def save(self, commit=True):
        # Process payment immediately and clear CVV
        cvv = self.cleaned_data.pop('cvv', None)
        instance = super().save(commit=commit)

        # Process payment only for new cards
        if not self.instance.pk and cvv:
            try:
                # Tokenize card with payment gateway
                token = self._process_payment(
                    self.cleaned_data['card_number'],
                    self.cleaned_data['expiry_date'],
                    cvv
                )
                # Save token to user profile for future use
                instance.token = token
                if commit:
                    instance.save()
            except Exception as e:
                logger.error(f"Payment processing failed: {str(e)}")
                raise ValidationError(
                    _("Payment method could not be processed. Please try again."),
                    code='payment_processing_error'
                )

        return instance


    def _process_payment(self, card_number, expiry, cvv):
        """Tokenize card with payment gateway (mock implementation)"""
        if settings.DEBUG:
            logger.debug(f"Mock payment processing for card: {card_number[-4:]}")
            return f"tok_mock_{card_number[-4:]}"
        else:
            # Implement real payment gateway integration here
            # Example:
            # import payment_gateway
            # return payment_gateway.tokenize(card_number, expiry, cvv)
            return f"tok_prod_{card_number[-4:]}"

class MobileMoneyVerificationForm(forms.Form):
    verification_code = forms.CharField(
        max_length=8,
        validators=[
            RegexValidator(
                regex='^[A-Z0-9]{8}$',
                message='Enter a valid 8-character verification code'
            )
        ],
        widget=forms.TextInput(attrs={
            'placeholder': 'Enter verification code',
            'class': 'form-control'
        })
    )


class MobilePaymentForm(forms.Form):
    PROVIDER_CHOICES = [
        ('MP', 'M-Pesa'),
        ('AT', 'Airtel Money'),
    ]

    provider = forms.ChoiceField(
        choices=PROVIDER_CHOICES,
        widget=forms.RadioSelect(attrs={'class': 'btn-check'})
    )

    phone_number = forms.CharField(
        validators=[
            RegexValidator(
                regex=r'^\+?2547\d{8}$',
                message="Enter a valid Kenyan phone number (e.g. 254712345678)"
            )
        ],
        widget=forms.TextInput(attrs={
            'placeholder': '2547XXXXXXXX',
            'class': 'form-control'
        })
    )

    def clean_phone_number(self):
        phone = self.cleaned_data['phone_number']
        return phone if phone.startswith('254') else f'254{phone[1:]}'