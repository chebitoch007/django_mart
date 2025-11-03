# orders/forms.py - ENHANCED VERSION

from django import forms
from django_countries.widgets import CountrySelectWidget
from .models import Order


class ShippingForm(forms.ModelForm):
    """
    Enhanced shipping form with HTML5 validation, autocomplete,
    and improved UX through proper input types and patterns.
    """

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

        # Custom widgets with HTML5 attributes for better UX
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
            # Use django-countries widget for country selection
            'country': CountrySelectWidget(attrs={
                'class': 'form-select',
                'autocomplete': 'country',
                'required': True,
            }),
            # NEW: Delivery instructions textarea
            'delivery_instructions': forms.Textarea(attrs={
                'placeholder': 'e.g., "Leave package at front door" or "Call upon arrival"',
                'class': 'form-control',
                'rows': 3,
                'maxlength': 200,
            }),
            # NEW: Billing same as shipping checkbox
            'billing_same_as_shipping': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
            }),
        }

        # Custom labels for better clarity
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

        # Help text for specific fields
        help_texts = {
            'phone': 'Include country code (e.g., +254 for Kenya)',
            'delivery_instructions': 'Maximum 200 characters',
            'billing_same_as_shipping': 'Check if your billing address matches your shipping address',
        }

    def clean_phone(self):
        """
        Validate and normalize phone number.
        Ensures phone starts with + and contains only digits.
        """
        phone = self.cleaned_data.get('phone', '').strip()

        # Remove spaces and dashes for validation
        phone_digits = phone.replace(' ', '').replace('-', '')

        # Ensure it starts with +
        if not phone_digits.startswith('+'):
            raise forms.ValidationError(
                "Phone number must start with country code (e.g., +254712345678)"
            )

        # Validate length (between 10 and 16 characters including +)
        if len(phone_digits) < 10 or len(phone_digits) > 16:
            raise forms.ValidationError(
                "Phone number must be between 9 and 15 digits (plus country code)"
            )

        return phone_digits

    def clean_email(self):
        """
        Validate and normalize email address.
        """
        email = self.cleaned_data.get('email', '').strip().lower()

        if not email:
            raise forms.ValidationError("Email address is required")

        return email

    def clean_delivery_instructions(self):
        """
        Validate delivery instructions don't exceed character limit.
        """
        instructions = self.cleaned_data.get('delivery_instructions', '').strip()

        if len(instructions) > 200:
            raise forms.ValidationError(
                f"Delivery instructions must be 200 characters or less. "
                f"Currently: {len(instructions)} characters."
            )

        return instructions

    def clean(self):
        """
        Form-wide validation.
        Can add cross-field validation here if needed.
        """
        cleaned_data = super().clean()

        # Example: Ensure postal code is provided for certain countries
        country = cleaned_data.get('country')
        postal_code = cleaned_data.get('postal_code', '').strip()

        # Countries that typically require postal codes
        postal_required_countries = ['US', 'GB', 'CA', 'AU', 'DE', 'FR']

        # country is returned as a string code (e.g., 'KE', 'US') by django-countries
        if country and str(country) in postal_required_countries and not postal_code:
            # Get country name for error message
            from django_countries import countries
            country_name = countries.name(country) if country else 'this country'
            self.add_error('postal_code', f'Postal code is required for {country_name}')

        return cleaned_data