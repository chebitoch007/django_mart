from django import forms
from django.core.validators import RegexValidator


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