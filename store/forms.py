# store/forms.py
from django import forms
from django.template.defaultfilters import slugify
from .models import Product, Category, ProductImage, Review
from django.core.exceptions import ValidationError
from .validators import validate_product_name
from django.forms import inlineformset_factory
from django.utils.html import format_html
from django.conf import settings
from urllib.parse import urlparse


class CategoryChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        depth = obj.mptt_level if hasattr(obj, 'mptt_level') else 0
        return f"{'—' * depth} {obj.name}"


class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ['rating', 'title', 'comment']
        widgets = {
            'rating': forms.NumberInput(attrs={'min': 1, 'max': 5}),
        }


# Formset with enhanced validation
class BaseProductImageFormSet(forms.BaseInlineFormSet):
    def clean(self):
        super().clean()
        # Check for duplicate colors
        colors = set()
        for form in self.forms:
            if not form.cleaned_data or form.cleaned_data.get('DELETE'):
                continue

            color_value = form.cleaned_data.get('color')
            # Handle None case before stripping
            color = color_value.strip().lower() if color_value else ''

            if color:
                if color in colors:
                    form.add_error('color', 'This color is already specified for another image')
                colors.add(color)


ProductImageFormSet = inlineformset_factory(
    Product,
    ProductImage,
    formset=BaseProductImageFormSet,
    fields=('image', 'color'),
    extra=3,
    can_delete=True,
    widgets={
        'image': forms.FileInput(attrs={'class': 'form-control'}),
        'color': forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., Red, Blue, Black'
        })
    }
)


class ProductForm(forms.ModelForm):
    name = forms.CharField(
        validators=[validate_product_name],
        help_text=format_html(
            '5-100 characters. Allowed: letters, numbers, spaces, and these symbols: '
            '<span class="font-mono">- \' " , . ( ) & ! ; : % + @ # ° * ¢ £ ¥ € © ® ™</span>'
        ),
        widget=forms.TextInput(attrs={
            'minlength': '5',
            'maxlength': '100',
            'pattern': r"[\w\s\-\'\",\.\(\)&!;:%+@#°*¢£¥€©®™]{5,100}",
            'title': '5-100 characters with allowed punctuation',
            'x-model': 'productName',
            '@input': 'updateSlugPreview()'
        })
    )

    category = CategoryChoiceField(
        queryset=Category.objects.all().select_related('parent'),
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    # Slug preview field (read-only)
    slug_preview = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'readonly': True,
            'class': 'form-control bg-gray-100'
        }),
        label="URL Slug Preview"
    )

    is_dropship = forms.BooleanField(
        required=False,
        label="Dropshipping Product",
        help_text="Check if this is an AliExpress dropshipping product"
    )

    aliexpress_url = forms.URLField(
        required=False,
        label="AliExpress Product URL",
        help_text="Paste the AliExpress product link to auto-fill details"
    )

    shipping_time = forms.CharField(
        required=False,
        max_length=50,
        initial="10-20 days",
        widget=forms.TextInput(attrs={'placeholder': 'e.g., 10-20 days'})
    )

    commission_rate = forms.DecimalField(
        required=False,
        max_digits=5,
        decimal_places=2,
        initial=15.00,
        widget=forms.NumberInput(attrs={'step': '0.01'})
    )


    class Meta:
        model = Product
        fields = [
            'name', 'category', 'description', 'short_description',
            'price', 'discount_price', 'stock', 'image',
            'available', 'featured', 'slug_preview',
            'is_dropship', 'aliexpress_url', 'shipping_time', 'commission_rate'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            'short_description': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
            'price': forms.NumberInput(attrs={'class': 'form-control pl-12'}),
            'discount_price': forms.NumberInput(attrs={'class': 'form-control pl-12'}),
            'stock': forms.NumberInput(attrs={'class': 'form-control'}),
            'image': forms.FileInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].queryset = Category.objects.all()

        # Initialize slug preview for existing products
        if self.instance and self.instance.pk:
            self.fields['slug_preview'].initial = self.instance.slug
        else:
            self.fields['slug_preview'].initial = 'generated-when-you-type'

        # Set required attribute for image only when creating new product
        if not self.instance.pk:
            self.fields['image'].required = True
        else:
            self.fields['image'].required = False

    def clean_aliexpress_url(self):
        url = self.cleaned_data.get('aliexpress_url')
        if url:
            parsed = urlparse(url)
            if 'aliexpress.com' not in parsed.netloc:
                raise ValidationError("Please enter a valid AliExpress URL")
        return url

    def clean(self):
        cleaned_data = super().clean()
        is_dropship = cleaned_data.get('is_dropship')
        aliexpress_url = cleaned_data.get('aliexpress_url')

        if is_dropship and not aliexpress_url:
            self.add_error(
                'aliexpress_url',
                "AliExpress URL is required for dropshipping products"
            )

        return cleaned_data


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

    def clean(self):
        cleaned_data = super().clean()
        discount_price = cleaned_data.get('discount_price')
        price = cleaned_data.get('price')

        # Ensure discount price is less than regular price
        if discount_price and price and discount_price >= price:
            self.add_error('discount_price', "Discount price must be lower than regular price")

        return cleaned_data

    def save(self, commit=True):
        # Generate slug only for new products
        if not self.instance.pk:
            self.instance.slug = self.generate_unique_slug(self.cleaned_data['name'])
        return super().save(commit)

    def generate_unique_slug(self, name):
        """Generate a unique slug based on product name"""
        base_slug = slugify(name)
        unique_slug = base_slug
        counter = 1

        while Product.objects.filter(slug=unique_slug).exists():
            unique_slug = f"{base_slug}-{counter}"
            counter += 1

        return unique_slug

class ImportProductsForm(forms.Form):
    url = forms.URLField(
        label='AliExpress Product URL',
        widget=forms.URLInput(attrs={
            'placeholder': 'https://www.aliexpress.com/item/...',
            'class': 'form-control'
        })
    )
    category = forms.ModelChoiceField(
        queryset=Category.objects.all(),
        label='Assign to Category',
        widget=forms.Select(attrs={'class': 'form-select'})
    )