from django import forms
from .models import CartItem

class CartAddProductForm(forms.ModelForm):
    class Meta:
        model = CartItem
        fields = ['quantity']
        widgets = {
            'quantity': forms.NumberInput(attrs={
                'min': 1,
                'class': 'form-control',
                'style': 'width: 70px;'
            })
        }