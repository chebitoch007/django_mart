# store/forms.py (file, not directory)

from django import forms
from .models import Product, Category, ProductImage, Review
from django.core.exceptions import ValidationError
import re
from django.forms import inlineformset_factory
from .validators import validate_product_name

class CategoryChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        depth = self.get_depth(obj)
        return f"{'—' * depth} {obj.name}"

    def get_depth(self, obj, depth=0):
        if obj.parent:
            return self.get_depth(obj.parent, depth + 1)
        return depth



class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ['rating', 'title', 'comment']
        widgets = {
            'rating': forms.NumberInput(attrs={'min': 1, 'max': 5}),
        }


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True

class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            return [single_file_clean(d, initial) for d in data]
        return single_file_clean(data, initial)



class ProductForm(forms.ModelForm):
    name = forms.CharField(
        validators=[validate_product_name],
        help_text="5-100 characters (letters, numbers, spaces, and common punctuation)"
    )
    category = CategoryChoiceField(
        queryset=Category.objects.all().select_related('parent'),
        widget=forms.Select(attrs={'style': 'width: 300px;'})
    )


    additional_images = MultipleFileField(
        required=False,
        label='Additional Images'
    )

    class Meta:
        model = Product
        fields = ['name', 'category', 'description', 'short_description',
                 'price', 'discount_price', 'stock', 'available', 'featured']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'short_description': forms.Textarea(attrs={'rows': 2}),
            'category': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].queryset = Category.objects.filter(parent__isnull=False)

        # Add Bootstrap classes to form fields
        for field_name, field in self.fields.items():
            if field_name != 'available' and field_name != 'featured':
                field.widget.attrs['class'] = 'form-control'
            if field_name in ['available', 'featured']:
                field.widget.attrs['class'] = 'form-check-input'

    def clean_price(self):
        price = self.cleaned_data.get('price')
        if price <= 0:
            raise ValidationError("Price must be greater than zero.")
        return price

    def clean_discount_price(self):
        discount_price = self.cleaned_data.get('discount_price')
        price = self.cleaned_data.get('price')

        if discount_price and price and discount_price >= price:
            raise ValidationError("Discount price must be lower than the regular price.")
        return discount_price

    def clean_name(self):
        name = self.cleaned_data.get('name')
        if not re.match(r'^[\w\s-]{5,100}$', name):
            raise ValidationError(
                "Product name must be 5-100 characters long and can only contain letters, numbers, spaces, and hyphens."
            )
        return name

    def clean_additional_images(self):
        files = self.cleaned_data.get('additional_images', [])
        for file in files:
            if file.size > 5 * 1024 * 1024:  # 5MB
                raise ValidationError(f"{file.name} is too large (max 5MB)")
            if not file.content_type.startswith('image/'):
                raise ValidationError(f"{file.name} is not a valid image file")
        return files

    def save(self, commit=True):
        product = super().save(commit=commit)

        # Save additional images
        images = self.cleaned_data.get('additional_images', [])
        for image in images:
            ProductImage.objects.create(product=product, image=image)

        return product

