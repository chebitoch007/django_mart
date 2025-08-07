from django import forms
from django.conf import settings
from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
import re
import datetime
import logging

from orders.models import Order
from payment.models import PaymentMethod, CURRENCY_CHOICES, Payment

logger = logging.getLogger(__name__)


# Simple Luhn checksum validation
def luhn_checksum(card_number: str) -> bool:
    """Return True if card_number passes the Luhn checksum."""
    def digits_of(n): return [int(d) for d in n]
    digits = digits_of(card_number)
    odd_sum = sum(digits[-1::-2])
    even_sum = sum(sum(digits_of(str(2 * d))) for d in digits[-2::-2])
    return (odd_sum + even_sum) % 10 == 0


class PaymentProcessingForm(forms.Form):
    order_id = forms.IntegerField()
    order = forms.IntegerField(required=False)
    payment_method = forms.CharField(max_length=20)
    amount = forms.DecimalField(max_digits=12, decimal_places=2)
    currency = forms.CharField(max_length=3)
    conversion_rate = forms.FloatField()

    # Optional fields
    phone_number = forms.CharField(required=False)
    card_data = forms.JSONField(required=False)
    idempotency_key = forms.UUIDField(required=False)

    # Stripe-related fields
    stripe_payment_intent_id = forms.CharField(required=False)
    payment_intent_client_secret = forms.CharField(required=False)

    # PayPal-related fields
    paypal_order_id = forms.CharField(required=False)
    paypal_payer_id = forms.CharField(required=False)

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        self.kwargs = kwargs  # Capture remaining keyword args
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned = super().clean()

        # --- ORDER VALIDATION ---
        order_id = cleaned.get('order_id') or cleaned.get('order') or self.kwargs.get('order_id')
        try:
            order = Order.objects.get(id=order_id)
        except (Order.DoesNotExist, TypeError):
            raise ValidationError("Invalid order ID")
        if order.user != self.user:
            raise ValidationError("Order does not belong to this user")
        cleaned['order'] = order

        # --- PAYMENT METHOD VALIDATION ---
        method = cleaned.get('payment_method', '').lower()
        try:
            enabled = [m.lower() for m in settings.ENABLED_PAYMENT_METHODS]
        except AttributeError:
            enabled = ['mpesa', 'airtel', 'card', 'paypal']
        if method not in enabled:
            raise ValidationError("This payment method is not currently available")

        # --- MOBILE MONEY ---
        if method in ('mpesa', 'airtel'):
            phone = cleaned.get('phone_number', '')
            if not phone:
                self.add_error('phone_number', 'Phone number is required for mobile payments')
            elif not re.match(r'^7\d{8}$', phone):
                self.add_error('phone_number', 'Invalid phone number format (e.g. 712345678)')

        # --- CARD (Stripe) ---
        elif method == 'card':
            card = cleaned.get('card_data')
            if card:
                required = {'number', 'expiry', 'cvv', 'name'}
                missing = required - set(card)
                if missing:
                    self.add_error('card_data', f'Missing fields: {missing}')
                else:
                    number = card.get('number', '').replace(' ', '')
                    if not luhn_checksum(number):
                        self.add_error('card_data', 'Invalid card number')
            elif not cleaned.get('stripe_payment_intent_id'):
                self.add_error('stripe_payment_intent_id', 'Stripe payment ID is missing')

        # --- PAYPAL ---
        elif method == 'paypal':
            # Validation handled at view level
            pass

        return cleaned

    def clean_amount(self):
        amount = self.cleaned_data['amount']
        if amount <= 0:
            raise forms.ValidationError("Invalid payment amount")
        return amount

    def clean_idempotency_key(self):
        key = self.cleaned_data.get('idempotency_key')
        if key and Payment.objects.filter(idempotency_key=key).exists():
            raise ValidationError("This payment has already been processed")
        return key

    def clean_payment_method(self):
        method = self.cleaned_data.get('payment_method', '').lower()
        allowed = ['mpesa', 'airtel', 'card', 'paypal']
        if method not in allowed:
            raise ValidationError("Invalid payment method")
        return method


class PaymentMethodForm(forms.ModelForm):
    # Never store CVV long-term - this is for temporary processing only
    cvv = forms.CharField(
        max_length=4,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '***',
            'maxlength': '4',
            'autocomplete': 'off',
            'aria-label': 'CVV security code'
        })
    )

    method_type = forms.ChoiceField(
        choices=(
            ('VISA', 'Visa'),
            ('MASTERCARD', 'MasterCard'),
            ('PAYPAL', 'PayPal'),
            ('MPESA', 'M-Pesa'),
            ('AIRTEL', 'Airtel Money'),
        ),
        widget=forms.RadioSelect(attrs={'class': 'payment-method-select'})
    )

    class Meta:
        model = PaymentMethod
        fields = ['method_type', 'cardholder_name', 'paypal_email', 'phone_number', 'is_default']
        widgets = {
            'method_type': forms.HiddenInput(),
            'cardholder_name': forms.TextInput(attrs={
                'class': 'form-control',
                'aria-label': 'Cardholder name'
            }),
            'paypal_email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'your@email.com'
            }),
            'phone_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Phone number'
            }),
            'is_default': forms.CheckboxInput(attrs={
                'aria-label': 'Set as default payment method'
            }),
        }
        labels = {
            'is_default': _('Set as default payment method'),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        # Card fields
        self.fields['card_number'] = forms.CharField(
            max_length=19,
            required=False,
            widget=forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '**** **** **** ****',
                'aria-label': 'Card number'
            })
        )
        self.fields['expiry_date'] = forms.CharField(
            max_length=7,
            required=False,
            widget=forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'MM/YY',
                'aria-label': 'Expiry date'
            })
        )

        # Set initial values if editing
        if self.instance.pk:
            if self.instance.method_type in ['VISA', 'MASTERCARD']:
                self.fields['card_number'].initial = self.instance.get_decrypted_card_number()
                self.fields['expiry_date'].initial = self.instance.get_decrypted_expiry_date()
                self.fields['cvv'].required = False
            elif self.instance.method_type == 'PAYPAL':
                self.fields['paypal_email'].initial = self.instance.paypal_email

        # Set initial method type
        if not self.instance.pk:
            self.fields['method_type'].initial = 'VISA'

    def clean(self):
        cleaned_data = super().clean()
        method_type = cleaned_data.get('method_type')

        if method_type in ['VISA', 'MASTERCARD']:
            # Card validation
            if not cleaned_data.get('card_number'):
                self.add_error('card_number', 'Card number is required')
            if not cleaned_data.get('expiry_date'):
                self.add_error('expiry_date', 'Expiry date is required')
            if not cleaned_data.get('cardholder_name'):
                self.add_error('cardholder_name', 'Cardholder name is required')

        elif method_type == 'PAYPAL':
            # PayPal validation
            if not cleaned_data.get('paypal_email'):
                self.add_error('paypal_email', 'PayPal email is required')

        elif method_type in ['MPESA', 'AIRTEL']:
            # Mobile money validation
            if not cleaned_data.get('phone_number'):
                self.add_error('phone_number', 'Phone number is required')

        return cleaned_data

    def clean_card_number(self):
        card_number = self.cleaned_data.get('card_number', '').replace(' ', '')
        if not card_number:
            return None

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
        expiry_date = self.cleaned_data.get('expiry_date', '')
        if not expiry_date:
            return None

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
            current_year = datetime.date.today().year % 100
            current_century = datetime.date.today().year // 100 * 100

            if year < 100:
                year += current_century
                if year < datetime.date.today().year:
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
                _("Please enter a valid expiration date in MM/YY format"),
                code='invalid_expiry'
            )

    def clean_cvv(self):
        cvv = self.cleaned_data.get('cvv', '')
        if not cvv:
            return None

        if not cvv.isdigit() or len(cvv) not in (3, 4):
            raise ValidationError(
                _("Please enter a valid CVV"),
                code='invalid_cvv'
            )
        return cvv

    def save(self, commit=True):
        instance = super().save(commit=False)
        method_type = self.cleaned_data.get('method_type')

        if method_type in ['VISA', 'MASTERCARD']:
            instance.encrypted_card_number = self.cleaned_data.get('card_number')
            instance.encrypted_expiry_date = self.cleaned_data.get('expiry_date')
            instance.encrypted_cvv = self.cleaned_data.get('cvv')
            instance.cardholder_name = self.cleaned_data.get('cardholder_name')

            # Determine card type
            card_number = self.cleaned_data.get('card_number', '')
            if card_number.startswith('4'):
                instance.card_type = 'visa'
            elif card_number.startswith('5'):
                instance.card_type = 'mastercard'
            else:
                instance.card_type = 'other'

        elif method_type == 'PAYPAL':
            instance.paypal_email = self.cleaned_data.get('paypal_email')

        elif method_type in ['MPESA', 'AIRTEL']:
            instance.phone_number = self.cleaned_data.get('phone_number')
            instance.provider_code = method_type

        # Set user
        if self.user:
            instance.user = self.user

        if commit:
            instance.save()

        return instance


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


class PayPalPaymentForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'placeholder': 'your@email.com',
            'class': 'form-control'
        })
    )
    save_method = forms.BooleanField(
        required=False,
        initial=True,
        label="Save payment method for future use"
    )




def clean_currency(self):
    currency = self.cleaned_data['currency']
    allowed_currencies = [c[0] for c in CURRENCY_CHOICES]
    if currency not in allowed_currencies:
        raise ValidationError("Invalid currency selected")
    return currency