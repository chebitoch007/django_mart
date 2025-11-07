# orders/forms.py

from django import forms
from django_countries.widgets import CountrySelectWidget
from .models import Order
from users.models import Address


class ShippingForm(forms.ModelForm):
    """
    Enhanced shipping form that integrates with saved user addresses.
    Allows selecting from saved addresses or entering new address.
    """

    # Additional field for address selection
    saved_address = forms.ModelChoiceField(
        queryset=Address.objects.none(),
        required=False,
        empty_label="Enter new address",
        widget=forms.Select(attrs={
            'class': 'form-select',
            'id': 'saved-address-select'
        }),
        label='Use Saved Address'
    )

    # Option to save current address
    save_address = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
            'id': 'save-address-checkbox'
        }),
        label='Save this address to my account for future orders'
    )

    # Address nickname for saved addresses
    address_nickname = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., Home, Office',
            'id': 'address-nickname-input'
        }),
        label='Address Nickname'
    )

    class Meta:
        model = Order
        fields = [
            'first_name',
            'last_name',
            'email',
            'phone',
            'address',
            'city',
            'postal_code',
            'state',
            'country',
            'delivery_instructions',
            'billing_same_as_shipping',
        ]

        widgets = {
            'first_name': forms.TextInput(attrs={
                'placeholder': 'First Name',
                'class': 'form-control',
                'autocomplete': 'given-name',
                'required': True,
            }),
            'last_name': forms.TextInput(attrs={
                'placeholder': 'Last Name',
                'class': 'form-control',
                'autocomplete': 'family-name',
                'required': True,
            }),
            'email': forms.EmailInput(attrs={
                'placeholder': 'Email Address',
                'class': 'form-control',
                'autocomplete': 'email',
                'required': True,
            }),
            'phone': forms.TextInput(attrs={
                'placeholder': '+254712345678',
                'class': 'form-control',
                'autocomplete': 'tel',
                'inputmode': 'tel',
                'pattern': r'^\+?1?\d{9,15}$',
                'title': 'Enter phone number with country code (e.g., +254712345678)',
                'required': True,
            }),
            'address': forms.TextInput(attrs={
                'placeholder': 'Street address, P.O. Box, or Apartment number',
                'class': 'form-control',
                'autocomplete': 'street-address',
                'required': True,
            }),
            'city': forms.TextInput(attrs={
                'placeholder': 'City or Town',
                'class': 'form-control',
                'autocomplete': 'address-level2',
                'required': True,
            }),
            'postal_code': forms.TextInput(attrs={
                'placeholder': 'Postal/ZIP Code',
                'class': 'form-control',
                'autocomplete': 'postal-code',
                'required': True,
            }),
            'state': forms.TextInput(attrs={
                'placeholder': 'State/Province/Region (optional)',
                'class': 'form-control',
                'autocomplete': 'address-level1',
            }),
            'country': CountrySelectWidget(attrs={
                'class': 'form-select',
                'autocomplete': 'country',
                'required': True,
            }),
            'delivery_instructions': forms.Textarea(attrs={
                'placeholder': 'e.g., "Leave package at front door" or "Call upon arrival"',
                'class': 'form-control',
                'rows': 3,
                'maxlength': 200,
            }),
            'billing_same_as_shipping': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
            }),
        }

        labels = {
            'first_name': 'First Name',
            'last_name': 'Last Name',
            'email': 'Email Address',
            'phone': 'Phone Number',
            'address': 'Street Address',
            'city': 'City',
            'postal_code': 'Postal Code',
            'state': 'State/Province',
            'country': 'Country',
            'delivery_instructions': 'Delivery Instructions (Optional)',
            'billing_same_as_shipping': 'Billing address same as shipping',
        }

        help_texts = {
            'phone': 'Include country code (e.g., +254 for Kenya)',
            'delivery_instructions': 'Maximum 200 characters',
            'billing_same_as_shipping': 'Check if your billing address matches your shipping address',
        }

    def __init__(self, *args, user=None, **kwargs):
        """
        Initialize form with user's saved addresses if authenticated.
        """
        super().__init__(*args, **kwargs)

        # If user is authenticated, populate saved addresses
        if user and user.is_authenticated:
            self.fields['saved_address'].queryset = Address.objects.filter(
                user=user
            ).order_by('-is_default', '-created')

            # Set default address as initial selection if exists
            default_address = Address.objects.filter(
                user=user,
                is_default=True
            ).first()

            if default_address:
                self.fields['saved_address'].initial = default_address
        else:
            # Hide address selection fields for anonymous users
            self.fields.pop('saved_address', None)
            self.fields.pop('save_address', None)
            self.fields.pop('address_nickname', None)

    def clean_phone(self):
        """Validate and normalize phone number."""
        phone = self.cleaned_data.get('phone', '').strip()
        phone_digits = phone.replace(' ', '').replace('-', '')

        if not phone_digits.startswith('+'):
            raise forms.ValidationError(
                "Phone number must start with country code (e.g., +254712345678)"
            )

        if len(phone_digits) < 10 or len(phone_digits) > 16:
            raise forms.ValidationError(
                "Phone number must be between 9 and 15 digits (plus country code)"
            )

        return phone_digits

    def clean_email(self):
        """Validate and normalize email address."""
        email = self.cleaned_data.get('email', '').strip().lower()
        if not email:
            raise forms.ValidationError("Email address is required")
        return email

    def clean_delivery_instructions(self):
        """Validate delivery instructions length."""
        instructions = self.cleaned_data.get('delivery_instructions', '').strip()
        if len(instructions) > 200:
            raise forms.ValidationError(
                f"Delivery instructions must be 200 characters or less. "
                f"Currently: {len(instructions)} characters."
            )
        return instructions

    def clean(self):
        """Form-wide validation."""
        cleaned_data = super().clean()

        # Check if save_address is checked but nickname is missing
        save_address = cleaned_data.get('save_address')
        address_nickname = cleaned_data.get('address_nickname', '').strip()

        if save_address and not address_nickname:
            self.add_error('address_nickname',
                           'Please provide a nickname when saving address')

        # Postal code validation for specific countries
        country = cleaned_data.get('country')
        postal_code = cleaned_data.get('postal_code', '').strip()

        postal_required_countries = ['US', 'GB', 'CA', 'AU', 'DE', 'FR']

        if country and str(country) in postal_required_countries and not postal_code:
            from django_countries import countries
            country_name = countries.name(country) if country else 'this country'
            self.add_error('postal_code', f'Postal code is required for {country_name}')

        return cleaned_data