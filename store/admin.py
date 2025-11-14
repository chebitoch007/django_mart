# store/admin.py - COMPLETE FILE

from django import forms
from moneyed import Money
from decimal import Decimal
from core.utils import get_exchange_rate
from django.conf import settings
from django.contrib import admin
from django.db.models import Count, F, ExpressionWrapper, FloatField, Sum, Q
from django.utils.html import format_html
from django.urls import reverse, path
from django.contrib.admin import SimpleListFilter
from django.db.models import Case, When, Value
from django.utils import timezone
from django.shortcuts import render, redirect
from django.contrib import messages
from .forms import ProductForm
from .models import (
    Category, Product, NewsletterSubscription,
    SearchLog, ProductImage, ProductVariant, Review,
    Brand, Supplier, StockNotification
)
from mptt.admin import DraggableMPTTAdmin


# ===== HELPER FUNCTIONS =====

def safe_money_display(money_obj, default_currency='KES'):
    """Safely display Money objects"""
    if money_obj is None:
        return "-"
    if hasattr(money_obj, 'amount'):
        return f"{money_obj.currency} {money_obj.amount:,.2f}"
    try:
        return f"{default_currency} {float(money_obj):,.2f}"
    except (TypeError, ValueError):
        return str(money_obj)


def safe_image_url(image_field):
    """Safely get image URL"""
    try:
        if image_field and image_field.name:
            return image_field.url
    except (ValueError, AttributeError):
        pass
    return None


# ===== UNREGISTER TO PREVENT CONFLICTS =====
for model in [Category, Product, NewsletterSubscription, SearchLog,
              ProductImage, ProductVariant, Review, Brand, Supplier, StockNotification]:
    if admin.site.is_registered(model):
        admin.site.unregister(model)


# ===== BULK PRICE UPDATE FORM =====

class BulkPriceUpdateForm(forms.Form):
    """Form for updating multiple product prices at once"""

    input_currency = forms.ChoiceField(
        choices=[(c, c) for c in settings.CURRENCIES],
        initial='USD',
        label='From Currency'
    )

    target_currency = forms.ChoiceField(
        choices=[(c, c) for c in settings.CURRENCIES],
        initial=settings.DEFAULT_CURRENCY,
        label='To Currency'
    )

    markup_percentage = forms.DecimalField(
        max_digits=5,
        decimal_places=2,
        initial=0,
        label='Markup %',
        help_text='Add this percentage to the converted price (e.g., 20 for 20% markup)'
    )

    apply_to_discount = forms.BooleanField(
        required=False,
        initial=False,
        label='Also convert discount prices'
    )


# ===== QUICK EDIT FORM FOR INLINE EDITING =====

class QuickEditProductForm(forms.ModelForm):
    """Simplified form for quick product updates with ALL fields"""

    # Currency conversion fields
    input_currency = forms.ChoiceField(
        choices=[(c, c) for c in settings.CURRENCIES],
        initial='USD',
        label='Input Currency',
        help_text='Select the currency you want to input the price in'
    )

    input_price = forms.DecimalField(
        max_digits=14,
        decimal_places=2,
        required=False,
        label='Price',
        help_text='Enter price in your selected currency'
    )

    input_discount_price = forms.DecimalField(
        max_digits=14,
        decimal_places=2,
        required=False,
        label='Discount Price',
        help_text='Enter discount price (optional)'
    )

    target_currency = forms.ChoiceField(
        choices=[(c, c) for c in settings.CURRENCIES],
        initial=settings.DEFAULT_CURRENCY,
        label='Convert To',
        help_text='Price will be converted to this currency'
    )

    shipping_cost = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        label='Shipping Cost',
        help_text='Enter shipping cost (0 for free shipping) in your selected Input Currency',
        widget=forms.NumberInput(attrs={
            'step': '0.01',
            'min': '0'
        })
    )

    free_shipping = forms.BooleanField(
        required=False,
        label='Free Shipping',
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
        })
    )

    class Meta:
        model = Product
        fields = [
            'name', 'short_description', 'description',
            'features', 'cta', 'seo_keywords',
            'input_currency', 'input_price', 'input_discount_price', 'target_currency',
            'stock', 'available', 'featured', 'category', 'brand',
            'shipping_cost', 'free_shipping',
            'supplier', 'supplier_url'
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'maxlength': '200'
            }),
            'short_description': forms.Textarea(attrs={
                'rows': 2,
                'class': 'form-control',
                'maxlength': '300',
                'placeholder': 'Brief product summary (max 300 characters)'
            }),
            'description': forms.Textarea(attrs={
                'rows': 4,
                'class': 'form-control',
                'placeholder': 'Full product description'
            }),
            'features': forms.Textarea(attrs={
                'rows': 6,
                'class': 'form-control feature-list-input',
                'placeholder': '• Feature 1\n• Feature 2\n• Feature 3'
            }),
            'cta': forms.TextInput(attrs={
                'class': 'form-control cta-input',
                'maxlength': '200',
                'placeholder': '🎮 Get yours today - Limited stock!'
            }),
            'seo_keywords': forms.TextInput(attrs={
                'class': 'form-control',
                'maxlength': '500',
                'placeholder': 'gaming, console, retro, portable'
            }),
            'stock': forms.NumberInput(attrs={'class': 'form-control'}),
            'supplier_url': forms.URLInput(attrs={
                'placeholder': 'https://supplier.com/product',
                'class': 'form-control'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.instance and self.instance.pk:
            # Pre-fill price fields
            if hasattr(self.instance.price, 'amount'):
                self.fields['input_price'].initial = self.instance.price.amount
                self.fields['input_currency'].initial = str(self.instance.price.currency)

            if self.instance.discount_price and hasattr(self.instance.discount_price, 'amount'):
                self.fields['input_discount_price'].initial = self.instance.discount_price.amount

            # Pre-fill shipping cost
            if self.instance.shipping_cost:
                initial_input_curr = self.fields['input_currency'].initial or 'USD'
                shipping_curr = str(self.instance.shipping_cost.currency)

                if shipping_curr == initial_input_curr:
                    self.fields['shipping_cost'].initial = self.instance.shipping_cost.amount
                else:
                    try:
                        rate = get_exchange_rate(shipping_curr, initial_input_curr)
                        converted_shipping = Decimal(str(self.instance.shipping_cost.amount)) * rate
                        self.fields['shipping_cost'].initial = round(converted_shipping, 2)
                    except Exception:
                        self.fields['shipping_cost'].initial = self.instance.shipping_cost.amount

            self.fields['free_shipping'].initial = self.instance.free_shipping

    def save(self, commit=True):
        instance = super().save(commit=False)

        # Currency conversion logic
        input_curr = self.cleaned_data.get('input_currency')
        target_curr = self.cleaned_data.get('target_currency')
        input_price = self.cleaned_data.get('input_price')
        input_discount = self.cleaned_data.get('input_discount_price')
        shipping_cost = self.cleaned_data.get('shipping_cost')
        free_shipping = self.cleaned_data.get('free_shipping')

        def convert_currency(amount, from_curr, to_curr):
            if amount is None:
                return None
            if from_curr == to_curr:
                return Decimal(str(amount))
            try:
                rate = get_exchange_rate(from_curr, to_curr)
                return Decimal(str(amount)) * rate
            except Exception:
                return Decimal(str(amount))

        # Convert prices
        if input_price is not None:
            converted_price = convert_currency(input_price, input_curr, target_curr)
            instance.price = Money(converted_price, target_curr)

        if input_discount is not None:
            converted_discount = convert_currency(input_discount, input_curr, target_curr)
            instance.discount_price = Money(converted_discount, target_curr)
        else:
            instance.discount_price = None

        # Shipping logic
        if free_shipping:
            instance.shipping_cost = Money(0, target_curr)
            instance.free_shipping = True
        elif shipping_cost is not None:
            converted_shipping = convert_currency(shipping_cost, input_curr, target_curr)
            instance.shipping_cost = Money(converted_shipping, target_curr)
            instance.free_shipping = False

        if commit:
            instance.save()

        return instance


# ===== CUSTOM FILTERS =====

class DiscountFilter(SimpleListFilter):
    title = 'discount status'
    parameter_name = 'discount'

    def lookups(self, request, model_admin):
        return (
            ('with_discount', 'With Discount'),
            ('without_discount', 'Without Discount'),
            ('high_discount', 'High Discount (>30%)'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'with_discount':
            return queryset.filter(discount_price__isnull=False)
        if self.value() == 'without_discount':
            return queryset.filter(discount_price__isnull=True)
        if self.value() == 'high_discount':
            return queryset.annotate(
                discount_percent=Case(
                    When(price__gt=0, then=ExpressionWrapper(
                        (F('price') - F('discount_price')) * 100 / F('price'),
                        output_field=FloatField()
                    )),
                    default=Value(0),
                    output_field=FloatField()
                )
            ).filter(discount_percent__gt=30)
        return queryset


class NoPriceFilter(SimpleListFilter):
    """Filter for products without prices set"""
    title = 'price status'
    parameter_name = 'price_status'

    def lookups(self, request, model_admin):
        return (
            ('no_price', 'No Price Set'),
            ('has_price', 'Has Price'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'no_price':
            return queryset.filter(Q(price=0) | Q(price__isnull=True))
        if self.value() == 'has_price':
            return queryset.filter(price__gt=0)
        return queryset


class ReviewStatusFilter(SimpleListFilter):
    title = 'review status'
    parameter_name = 'status'

    def lookups(self, request, model_admin):
        return (
            ('approved', 'Approved'),
            ('pending', 'Pending Approval'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'approved':
            return queryset.filter(approved=True)
        if self.value() == 'pending':
            return queryset.filter(approved=False)


class SubscriptionStatusFilter(SimpleListFilter):
    title = 'subscription status'
    parameter_name = 'sub_status'

    def lookups(self, request, model_admin):
        return (
            ('active', 'Active Subscribers'),
            ('pending', 'Pending Confirmation'),
            ('unsubscribed', 'Unsubscribed'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'active':
            return queryset.filter(confirmed=True, unsubscribed=False)
        if self.value() == 'pending':
            return queryset.filter(confirmed=False, unsubscribed=False)
        if self.value() == 'unsubscribed':
            return queryset.filter(unsubscribed=True)


# ===== CATEGORY ADMIN =====

@admin.register(Category)
class CategoryAdmin(DraggableMPTTAdmin):
    mptt_indent_field = "name"
    list_display = ('tree_actions', 'indented_title', 'is_active', 'product_count', 'level_display')
    list_display_links = ('indented_title',)
    list_filter = ('is_active', 'parent')
    search_fields = ('name', 'description')
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ('meta_preview', 'created_at', 'updated_at')
    fieldsets = (
        (None, {
            'fields': ('parent', 'name', 'slug')
        }),
        ('Content', {
            'fields': ('description', 'image')
        }),
        ('SEO', {
            'fields': ('meta_title', 'meta_description', 'meta_preview'),
            'classes': ('collapse',)
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(_product_count=Count('products'))

    def product_count(self, instance):
        return instance._product_count

    product_count.admin_order_field = '_product_count'
    product_count.short_description = 'Products'

    def level_display(self, instance):
        return f"Level {instance.mptt_level}"

    level_display.short_description = 'Tree Level'

    def meta_preview(self, instance):
        if not instance.meta_title or not instance.meta_description:
            return format_html('<p style="color: #dc2626;">⚠️ Please add meta information for SEO</p>')

        return format_html(
            '<div style="border: 1px solid #ddd; padding: 15px; border-radius: 8px; max-width: 600px; '
            'background: #f9fafb; font-family: Arial, sans-serif;">'
            '<div style="color: #1a0dab; font-size: 18px; margin-bottom: 5px; font-weight: 500;">{}</div>'
            '<div style="color: #006621; font-size: 14px; margin-bottom: 8px;">{}</div>'
            '<div style="color: #545454; font-size: 14px; line-height: 1.5;">{}</div>'
            '</div>',
            instance.meta_title,
            f"https://yoursite.com{reverse('store:product_list_by_category', args=[instance.slug])}",
            instance.meta_description
        )

    meta_preview.short_description = 'Google Search Preview'


# ===== BRAND ADMIN =====

@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'product_count']
    search_fields = ['name']
    prepopulated_fields = {'slug': ('name',)}

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(_product_count=Count('products'))

    def product_count(self, instance):
        return instance._product_count

    product_count.admin_order_field = '_product_count'
    product_count.short_description = 'Products'


# ===== SUPPLIER ADMIN =====

@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ['name', 'website', 'product_count']
    search_fields = ['name', 'website']
    list_filter = ['name']

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(_product_count=Count('products'))

    def product_count(self, instance):
        return instance._product_count

    product_count.admin_order_field = '_product_count'
    product_count.short_description = 'Products'


# ===== ENHANCED PRODUCT ADMIN =====

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    form = ProductForm

    list_display = [
        'image_preview', 'name', 'category_link', 'brand', 'price_display',
        'discount_badge', 'shipping_display', 'stock_status', 'available',
        'rating_display', 'review_count', 'quick_edit_button'
    ]

    list_filter = [
        'available', 'featured', 'is_dropship',
        NoPriceFilter, DiscountFilter,
        'category__parent', 'brand'
    ]

    list_editable = ['available']

    readonly_fields = [
        'rating', 'review_count', 'created', 'updated',
        'search_vector_info', 'product_images_preview', 'variants_preview',
        'image_preview_large', 'price_conversion_calculator',
        'features_preview', 'marketing_preview'
    ]

    search_fields = ['name', 'description', 'short_description', 'slug', 'features', 'seo_keywords']
    autocomplete_fields = ['category', 'brand', 'supplier']

    actions = [
        'bulk_price_update',
        'convert_prices_to_kes',
        'apply_markup',
        'duplicate_products'
    ]

    fieldsets = (
        ('Basic Information', {
            'fields': ('category', 'brand', 'name', 'slug', 'short_description', 'description')
        }),
        ('✨ Product Features & Marketing', {
            'fields': ('features', 'features_preview', 'cta', 'seo_keywords', 'marketing_preview'),
            'description': 'Enhanced product details for better conversion and SEO'
        }),
        ('💰 Pricing & Currency Conversion', {
            'fields': ('price_conversion_calculator', 'price', 'discount_price')
        }),
        ('📦 Shipping Information', {
            'fields': ('shipping_cost', 'free_shipping', 'shipping_time'),
            'classes': ('collapse',)
        }),
        ('Inventory', {
            'fields': ('stock', 'available', 'featured')
        }),
        ('Main Image', {
            'fields': ('image', 'image_preview_large')
        }),
        ('Additional Images & Variants', {
            'fields': ('product_images_preview', 'variants_preview'),
            'classes': ('collapse',)
        }),
        ('Product Features', {
            'fields': ('rating', 'review_count')
        }),
        ('Dropshipping & Supplier', {
            'fields': (
                'is_dropship', 'supplier', 'supplier_url',
                'commission_rate', 'supplier_product_id'
            ),
            'classes': ('collapse',)
        }),
        ('Technical Information', {
            'fields': ('search_vector_info', 'created', 'updated'),
            'classes': ('collapse',)
        }),
    )

    def features_preview(self, obj):
        """Display features as formatted bullet list"""
        try:
            features = obj.get_features_list()
        except AttributeError:
            features = [f.strip() for f in (obj.features or "").split('\n') if f.strip()]

        if not features:
            return format_html('<p style="color: #9ca3af;">No features added</p>')

        html = '<div style="background: #f8fafc; padding: 15px; border-radius: 8px; border: 1px solid #e2e8f0;">'
        html += '<ul style="margin: 0; padding-left: 20px;">'
        for feature in features:
            # Remove bullet points from feature text
            clean_feature = feature.lstrip('•-*').strip()
            html += f'<li style="margin: 5px 0; color: #334155;">{clean_feature}</li>'
        html += '</ul></div>'
        return format_html(html)

    features_preview.short_description = 'Features Preview'

    def marketing_preview(self, obj):
        """Display marketing fields preview"""
        html = '<div style="background: #f0f9ff; padding: 20px; border-radius: 12px; border: 2px solid #3b82f6;">'

        # CTA Preview
        if obj.cta:
            html += '<div style="margin-bottom: 15px;">'
            html += '<strong style="color: #1e40af; display: block; margin-bottom: 8px;">📣 Call to Action:</strong>'
            html += f'<div style="background: linear-gradient(135deg, #fef3c7, #fde68a); padding: 12px; border-radius: 8px; font-weight: 600; color: #92400e;">{obj.cta}</div>'
            html += '</div>'

        # SEO Keywords Preview
        if obj.seo_keywords:
            html += '<div>'
            html += '<strong style="color: #1e40af; display: block; margin-bottom: 8px;">🔍 SEO Keywords:</strong>'
            html += '<div style="display: flex; flex-wrap: wrap; gap: 6px;">'
            keywords = [k.strip() for k in obj.seo_keywords.split(',') if k.strip()]
            for keyword in keywords:
                html += f'<span style="background: #dbeafe; color: #1e40af; padding: 4px 10px; border-radius: 12px; font-size: 12px; font-weight: 600;">{keyword}</span>'
            html += '</div></div>'

        if not obj.cta and not obj.seo_keywords:
            html += '<p style="color: #64748b; margin: 0;">⚠️ No marketing content added yet</p>'

        html += '</div>'
        return format_html(html)

    marketing_preview.short_description = 'Marketing Content Preview'

    def shipping_display(self, obj):
        """Display shipping cost with badge"""
        if obj.free_shipping or (obj.shipping_cost and obj.shipping_cost.amount == 0):
            return format_html(
                '<span style="background: #10b981; color: white; padding: 4px 8px; '
                'border-radius: 4px; font-size: 12px; font-weight: 600;">FREE</span>'
            )
        elif obj.shipping_cost:
            return format_html(
                '<span style="font-weight: 600; color: #059669;">{} {}</span>',
                obj.shipping_cost.currency,
                f"{obj.shipping_cost.amount:,.2f}"
            )
        return format_html('<span style="color: #9ca3af;">Not set</span>')

    shipping_display.short_description = 'Shipping'

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                '<path:object_id>/quick-edit/',
                self.admin_site.admin_view(self.quick_edit_view),
                name='store_product_quickedit'
            ),
            path(
                'bulk_price_update/',
                self.admin_site.admin_view(self.bulk_price_update_view),
                name='store_product_bulkprice'
            ),
        ]
        return custom_urls + urls

    def quick_edit_view(self, request, object_id):
        """Quick edit view with currency conversion"""
        product = self.get_object(request, object_id)

        if request.method == 'POST':
            form = QuickEditProductForm(request.POST, instance=product)
            if form.is_valid():
                form.save()
                messages.success(request, f'✅ Successfully updated {product.name}')
                return redirect('admin:store_product_changelist')
        else:
            form = QuickEditProductForm(instance=product)

        context = {
            'form': form,
            'product': product,
            'title': f'Quick Edit: {product.name}',
            'opts': self.model._meta,
            'has_view_permission': self.has_view_permission(request, product),
            'has_change_permission': self.has_change_permission(request, product),
        }

        return render(request, 'admin/store/product/quick_edit.html', context)

    def bulk_price_update_view(self, request):
        """Bulk update prices for selected products"""

        if request.method == 'POST':
            form = BulkPriceUpdateForm(request.POST)
            if form.is_valid():
                product_ids_str = request.POST.get('product_ids')
                if not product_ids_str:
                    messages.error(request, "No products were selected.")
                    return redirect('admin:store_product_changelist')

                product_ids = product_ids_str.split(',')
                products = Product.objects.filter(id__in=product_ids)

                input_curr = form.cleaned_data['input_currency']
                target_curr = form.cleaned_data['target_currency']
                markup = form.cleaned_data['markup_percentage']
                apply_discount = form.cleaned_data['apply_to_discount']

                rate = get_exchange_rate(input_curr, target_curr)
                updated_count = 0

                for product in products:
                    if hasattr(product.price, 'amount') and product.price.amount > 0:
                        base_amount = product.price.amount
                        converted = Decimal(str(base_amount)) * rate

                        if markup > 0:
                            converted = converted * (1 + markup / 100)

                        product.price = Money(converted, target_curr)

                        if apply_discount and product.discount_price:
                            discount_amount = product.discount_price.amount
                            converted_discount = Decimal(str(discount_amount)) * rate
                            if markup > 0:
                                converted_discount = converted_discount * (1 + markup / 100)
                            product.discount_price = Money(converted_discount, target_curr)

                        product.save()
                        updated_count += 1

                messages.success(
                    request,
                    f'✅ Successfully updated prices for {updated_count} products from {input_curr} to {target_curr}'
                )
                return redirect('admin:store_product_changelist')
            else:
                product_ids = request.POST.get('product_ids')
        else:
            form = BulkPriceUpdateForm()
            product_ids = request.GET.get('ids')

        context = {
            'form': form,
            'title': 'Bulk Price Update with Currency Conversion',
            'opts': self.model._meta,
            'product_ids': product_ids,
        }

        return render(request, 'admin/store/product/bulk_price_update.html', context)

    def image_preview(self, obj):
        """Safe image preview"""
        url = safe_image_url(obj.image)
        if url:
            return format_html(
                '<img src="{}" style="max-height: 50px; max-width: 50px; border-radius: 4px; object-fit: cover;" />',
                url
            )
        return "No image"

    image_preview.short_description = 'Image'

    def image_preview_large(self, obj):
        """Safe large image preview"""
        url = safe_image_url(obj.image)
        if url:
            return format_html(
                '<img src="{}" style="max-height: 400px; max-width: 400px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);" />',
                url
            )
        return "No image"

    image_preview_large.short_description = 'Product Image'

    def category_link(self, obj):
        url = reverse('admin:store_category_change', args=[obj.category.id])
        return format_html('<a href="{}">{}</a>', url, obj.category)

    category_link.short_description = 'Category'
    category_link.admin_order_field = 'category__name'

    def price_display(self, obj):
        """Display price with proper Money handling"""
        if not obj.price or (hasattr(obj.price, 'amount') and obj.price.amount == 0):
            return format_html(
                '<span style="background: #fee2e2; color: #991b1b; padding: 4px 8px; '
                'border-radius: 4px; font-weight: 600;">⚠️ No Price</span>'
            )

        if hasattr(obj.price, 'amount'):
            price_val = f"{obj.price.currency} {obj.price.amount:,.2f}"
        else:
            price_val = str(obj.price)

        if obj.discount_price:
            if hasattr(obj.discount_price, 'amount'):
                discount_val = f"{obj.discount_price.currency} {obj.discount_price.amount:,.2f}"
            else:
                discount_val = str(obj.discount_price)

            return format_html(
                '<span style="text-decoration: line-through; color: #9ca3af;">{}</span><br>'
                '<span style="color: #dc2626; font-weight: 600;">{}</span>',
                price_val,
                discount_val
            )

        return format_html('<span style="font-weight: 600; color: #059669;">{}</span>', price_val)

    price_display.short_description = 'Price'

    def discount_badge(self, obj):
        percent = obj.get_discount_percentage()
        if percent > 0:
            return format_html(
                '<span style="background: #dc2626; color: white; padding: 4px 8px; '
                'border-radius: 4px; font-size: 12px; font-weight: 600;">-{}%</span>',
                percent
            )
        return "-"

    discount_badge.short_description = 'Discount'

    def stock_status(self, obj):
        if obj.stock > 20:
            color = '#10b981'
            icon = '✓'
            text = f'In Stock ({obj.stock})'
        elif obj.stock > 0:
            color = '#f59e0b'
            icon = '⚠'
            text = f'Low ({obj.stock})'
        else:
            color = '#dc2626'
            icon = '✗'
            text = 'Out of Stock'

        return format_html(
            '<span style="color: {}; font-weight: 600;">{} {}</span>',
            color, icon, text
        )

    stock_status.short_description = 'Stock'

    def rating_display(self, obj):
        stars = '★' * int(obj.rating) + '☆' * (5 - int(obj.rating))
        rating_str = f"{float(obj.rating):.1f}"

        return format_html(
            '<span style="color: #fbbf24; font-size: 16px;">{}</span> <span style="color: #6b7280;">({})</span>',
            stars, rating_str
        )

    rating_display.short_description = 'Rating'

    def quick_edit_button(self, obj):
        """Display quick edit button"""
        url = reverse('admin:store_product_quickedit', args=[obj.pk])
        return format_html(
            '<a href="{}" class="button" style="background: #3b82f6; color: white; '
            'padding: 6px 12px; border-radius: 4px; text-decoration: none; font-size: 12px;">'
            '⚡ Quick Edit</a>',
            url
        )

    quick_edit_button.short_description = 'Actions'

    def price_conversion_calculator(self, obj):
        """Display interactive price conversion calculator"""
        current_price = safe_money_display(obj.price) if obj.price else "Not set"
        current_discount = safe_money_display(obj.discount_price) if obj.discount_price else "Not set"

        currencies = ', '.join(settings.CURRENCIES)

        return format_html(
            '''
            <div style="background: #f3f4f6; padding: 20px; border-radius: 8px; margin: 10px 0;">
                <h3 style="margin-top: 0; color: #1f2937;">💱 Currency Conversion Calculator</h3>

                <div style="background: white; padding: 15px; border-radius: 6px; margin-bottom: 15px;">
                    <strong>Current Prices:</strong><br>
                    Regular: <span style="color: #059669; font-weight: 600;">{}</span><br>
                    Discount: <span style="color: #dc2626; font-weight: 600;">{}</span>
                </div>

                <div style="background: #dbeafe; padding: 15px; border-radius: 6px;">
                    <p style="margin-top: 0;"><strong>💡 How to update prices:</strong></p>
                    <ol style="margin: 10px 0; padding-left: 20px;">
                        <li>Use the form fields to enter prices in any currency (USD, EUR, etc.)</li>
                        <li>Select your target currency (default: {})</li>
                        <li>Prices will be automatically converted when you save</li>
                    </ol>
                    <p style="margin-bottom: 0; font-size: 12px; color: #1e40af;">
                        📌 Supported currencies: {}
                    </p>
                </div>
            </div>
            ''',
            current_price,
            current_discount,
            settings.DEFAULT_CURRENCY,
            currencies
        )

    price_conversion_calculator.short_description = 'Price Calculator'

    def search_vector_info(self, obj):
        if obj.search_vector:
            return format_html('<span style="color: #10b981;">✓ Indexed</span>')
        return format_html('<span style="color: #dc2626;">✗ Not Indexed</span>')

    search_vector_info.short_description = 'Search Index'

    def product_images_preview(self, obj):
        images = obj.additional_images.all()[:6]
        if not images:
            return "No additional images"

        html = '<div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; max-width: 600px;">'
        for img in images:
            url = safe_image_url(img.image)
            if url:
                html += f'''
                <div style="position: relative;">
                    <img src="{url}" style="width: 100%; height: 150px; object-fit: cover; border-radius: 8px; border: 2px solid #e5e7eb;" />
                    <div style="text-align: center; margin-top: 5px; font-size: 12px; color: #6b7280;">
                        {img.color or "No color"}
                    </div>
                </div>
                '''
        html += '</div>'
        return format_html(html)

    product_images_preview.short_description = 'Additional Images'

    def variants_preview(self, obj):
        """Display product variants with safe price handling"""
        variants = obj.variants.all()[:10]
        if not variants:
            return format_html('<p style="color: #9ca3af;">No variants available</p>')

        html = '<table style="width: 100%; border-collapse: collapse;">'
        html += '<tr style="background: #f3f4f6;"><th style="padding: 8px; text-align: left;">Color</th><th style="padding: 8px; text-align: left;">Size</th><th style="padding: 8px; text-align: left;">Price</th><th style="padding: 8px; text-align: left;">Stock</th></tr>'

        for v in variants:
            stock_color = '#10b981' if v.quantity > 10 else '#f59e0b' if v.quantity > 0 else '#dc2626'
            price_str = safe_money_display(v.price)
            html += f'''
            <tr style="border-bottom: 1px solid #e5e7eb;">
                <td style="padding: 8px;">{v.color or "-"}</td>
                <td style="padding: 8px;">{v.size or "-"}</td>
                <td style="padding: 8px; font-weight: 600;">{price_str}</td>
                <td style="padding: 8px; color: {stock_color}; font-weight: 600;">{v.quantity}</td>
            </tr>
            '''
        html += '</table>'
        return format_html(html)

    variants_preview.short_description = 'Product Variants'

    # ===== ADMIN ACTIONS =====
    @admin.action(description='🔄 Convert prices (bulk)')
    def bulk_price_update(self, request, queryset):
        """Redirect to bulk price update page"""
        selected = queryset.values_list('id', flat=True)
        base_url = reverse('admin:store_product_bulkprice')
        redirect_url = f"{base_url}?ids={','.join(map(str, selected))}"
        return redirect(redirect_url)

    @admin.action(description='💱 Convert all to KES')
    def convert_prices_to_kes(self, request, queryset):
        """Quick convert to KES"""
        updated = 0
        for product in queryset:
            if product.price and hasattr(product.price, 'currency'):
                if str(product.price.currency) != 'KES':
                    rate = get_exchange_rate(str(product.price.currency), 'KES')
                    converted = Decimal(str(product.price.amount)) * rate
                    product.price = Money(converted, 'KES')

                    if product.discount_price:
                        disc_rate = get_exchange_rate(str(product.discount_price.currency), 'KES')
                        converted_disc = Decimal(str(product.discount_price.amount)) * disc_rate
                        product.discount_price = Money(converted_disc, 'KES')

                    product.save()
                    updated += 1

        self.message_user(request, f'✅ Converted {updated} products to KES')

    @admin.action(description='📈 Apply 20% markup')
    def apply_markup(self, request, queryset):
        """Apply 20% markup to selected products"""
        updated = 0
        for product in queryset:
            if product.price and hasattr(product.price, 'amount'):
                new_amount = product.price.amount * Decimal('1.20')
                product.price = Money(new_amount, product.price.currency)

                if product.discount_price:
                    new_discount = product.discount_price.amount * Decimal('1.20')
                    product.discount_price = Money(new_discount, product.discount_price.currency)

                product.save()
                updated += 1

        self.message_user(request, f'✅ Applied 20% markup to {updated} products')

    @admin.action(description='📋 Duplicate selected products')
    def duplicate_products(self, request, queryset):
        """Duplicate products for quick variations"""
        duplicated = 0
        for product in queryset:
            product.pk = None
            product.slug = None
            product.name = f"{product.name} (Copy)"
            product.save()
            duplicated += 1

        self.message_user(request, f'✅ Duplicated {duplicated} products')


# ===== PRODUCT IMAGE ADMIN =====

@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    list_display = ['product_link', 'image_preview', 'color', 'is_featured', 'created_at']
    list_filter = ['is_featured', 'color', 'created_at']
    search_fields = ['product__name', 'color']
    list_editable = ['is_featured', 'color']
    readonly_fields = ['image_preview_large', 'created_at']
    autocomplete_fields = ['product']

    def product_link(self, obj):
        url = reverse('admin:store_product_change', args=[obj.product.id])
        return format_html('<a href="{}">{}</a>', url, obj.product)

    product_link.short_description = 'Product'

    def image_preview(self, obj):
        """Safe image preview"""
        url = safe_image_url(obj.image)
        if url:
            return format_html(
                '<img src="{}" style="max-height: 60px; max-width: 60px; border-radius: 4px; object-fit: cover;" />',
                url
            )
        return "No image"

    image_preview.short_description = 'Preview'

    def image_preview_large(self, obj):
        """Safe large image preview"""
        url = safe_image_url(obj.image)
        if url:
            return format_html(
                '<img src="{}" style="max-height: 400px; max-width: 400px; border-radius: 8px;" />',
                url
            )
        return "No image"

    image_preview_large.short_description = 'Full Image'


# ===== PRODUCT VARIANT ADMIN =====

@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display = ['product_link', 'color', 'size', 'price_display', 'quantity', 'stock_badge']
    list_filter = ['color', 'product__category']
    search_fields = ['product__name', 'color', 'size']
    list_editable = ['quantity', 'color', 'size']
    autocomplete_fields = ['product']

    def product_link(self, obj):
        url = reverse('admin:store_product_change', args=[obj.product.id])
        return format_html('<a href="{}">{}</a>', url, obj.product)

    product_link.short_description = 'Product'

    def price_display(self, obj):
        """Display variant price"""
        return safe_money_display(obj.price)

    price_display.short_description = 'Price'

    def stock_badge(self, obj):
        if obj.quantity > 10:
            return format_html('<span style="color: #10b981; font-weight: 600;">✓ In Stock</span>')
        elif obj.quantity > 0:
            return format_html('<span style="color: #f59e0b; font-weight: 600;">⚠ Low ({})</span>', obj.quantity)
        return format_html('<span style="color: #dc2626; font-weight: 600;">✗ Out</span>')

    stock_badge.short_description = 'Status'


# ===== REVIEW ADMIN =====

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ['product_link', 'user', 'rating_stars', 'title', 'approved', 'helpful_count', 'created']
    list_filter = ['rating', 'approved', ReviewStatusFilter, 'created']
    search_fields = ['product__name', 'user__username', 'title', 'comment']
    list_editable = ['approved']
    readonly_fields = ['created', 'updated', 'rating_stars_display', 'helpful_voters_list']
    date_hierarchy = 'created'

    fieldsets = (
        ('Review Content', {
            'fields': ('product', 'user', 'rating_stars_display', 'title', 'comment')
        }),
        ('Engagement', {
            'fields': ('helpful_count', 'helpful_voters_list')
        }),
        ('Status', {
            'fields': ('approved',)
        }),
        ('Metadata', {
            'fields': ('created', 'updated'),
            'classes': ('collapse',)
        }),
    )

    def product_link(self, obj):
        url = reverse('admin:store_product_change', args=[obj.product.id])
        return format_html('<a href="{}">{}</a>', url, obj.product.name)

    product_link.short_description = 'Product'

    def rating_stars(self, obj):
        return f"{'★' * obj.rating}{'☆' * (5 - obj.rating)}"

    rating_stars.short_description = 'Rating'

    def rating_stars_display(self, obj):
        stars = '★' * obj.rating + '☆' * (5 - obj.rating)
        return format_html('<span style="color: #fbbf24; font-size: 20px;">{}</span>', stars)

    rating_stars_display.short_description = 'Rating'

    def helpful_voters_list(self, obj):
        voters = obj.helpful_voters.all()[:10]
        if not voters:
            return "No votes yet"
        return format_html(
            ', '.join([f'<a href="{reverse("admin:users_customuser_change", args=[v.id])}">{v.username}</a>' for v in
                       voters]))

    helpful_voters_list.short_description = 'Helpful Voters'


# ===== NEWSLETTER SUBSCRIPTION ADMIN =====

@admin.register(NewsletterSubscription)
class NewsletterSubscriptionAdmin(admin.ModelAdmin):
    list_display = ['email', 'status_badge', 'confirmed_at', 'created_at', 'source_display']
    search_fields = ['email', 'ip_address']
    list_filter = ['confirmed', 'unsubscribed', SubscriptionStatusFilter, 'created_at']
    readonly_fields = [
        'confirmation_token', 'unsubscribe_token', 'confirmation_sent',
        'confirmed_at', 'created_at', 'ip_address', 'source_url', 'days_since_signup'
    ]
    date_hierarchy = 'created_at'

    fieldsets = (
        ('Subscriber Information', {
            'fields': ('email', 'ip_address', 'source_url')
        }),
        ('Status', {
            'fields': ('confirmed', 'unsubscribed', 'days_since_signup')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'confirmation_sent', 'confirmed_at')
        }),
        ('Tokens (Read Only)', {
            'fields': ('confirmation_token', 'unsubscribe_token'),
            'classes': ('collapse',)
        }),
    )

    def status_badge(self, obj):
        if obj.unsubscribed:
            return format_html(
                '<span style="background: #dc2626; color: white; padding: 4px 12px; border-radius: 4px; font-weight: 600;">Unsubscribed</span>')
        if obj.confirmed:
            return format_html(
                '<span style="background: #10b981; color: white; padding: 4px 12px; border-radius: 4px; font-weight: 600;">✓ Active</span>')
        return format_html(
            '<span style="background: #f59e0b; color: white; padding: 4px 12px; border-radius: 4px; font-weight: 600;">⏳ Pending</span>')

    status_badge.short_description = 'Status'

    def source_display(self, obj):
        if obj.source_url:
            return format_html('<a href="{}" target="_blank">View Source</a>', obj.source_url)
        return "Direct"

    source_display.short_description = 'Source'

    def days_since_signup(self, obj):
        delta = timezone.now() - obj.created_at
        return f"{delta.days} days ago"

    days_since_signup.short_description = 'Signup Age'


# ===== SEARCH LOG ADMIN =====

@admin.register(SearchLog)
class SearchLogAdmin(admin.ModelAdmin):
    list_display = ['query', 'created_at', 'ip_address', 'result_estimate']
    list_filter = ['created_at']
    search_fields = ['query', 'ip_address']
    readonly_fields = ['created_at', 'ip_address']
    date_hierarchy = 'created_at'

    def result_estimate(self, obj):
        count = Product.objects.filter(
            Q(name__icontains=obj.query) |
            Q(description__icontains=obj.query)
        ).count()
        return f"~{count} results"

    result_estimate.short_description = 'Estimated Results'


# ===== STOCK NOTIFICATION ADMIN =====

@admin.register(StockNotification)
class StockNotificationAdmin(admin.ModelAdmin):
    list_display = ['email', 'product_link', 'created_at']
    list_filter = ['created_at']
    search_fields = ['email', 'product__name']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'

    def product_link(self, obj):
        url = reverse('admin:store_product_change', args=[obj.product.id])
        return format_html('<a href="{}">{}</a>', url, obj.product.name)

    product_link.short_description = 'Product'


# ===== CUSTOM ADMIN SITE CONFIGURATION =====

admin.site.site_header = "ASAI Admin Dashboard"
admin.site.site_title = "ASAI Admin"
admin.site.index_title = "Welcome to ASAI Administration"