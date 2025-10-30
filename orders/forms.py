# orders/forms.py

from django import forms
from .models import Order

class ShippingForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = [
            'first_name', 'last_name', 'email', 'phone',
            'address', 'city', 'postal_code', 'country'
        ]
        widgets = {
            'first_name': forms.TextInput(attrs={'placeholder': 'First Name', 'class':'form-control'}),
            'last_name':  forms.TextInput(attrs={'placeholder': 'Last Name',  'class':'form-control'}),
            'email':     forms.EmailInput(attrs={'placeholder': 'Email Address', 'class':'form-control'}),
            'phone':     forms.TextInput(attrs={'placeholder': 'Phone (e.g. +254 …)', 'class':'form-control'}),
            'address':   forms.TextInput(attrs={'placeholder': 'Street Address or P.O. Box', 'class':'form-control'}),
            'city':      forms.TextInput(attrs={'placeholder': 'City/Town', 'class':'form-control'}),
            'postal_code': forms.TextInput(attrs={'placeholder': 'Postal Code', 'class':'form-control'}),
            'country':   forms.Select(attrs={'class':'form-select'}),
        }
