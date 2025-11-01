# store/admin.py - COMPLETE FIXED VERSION
from django.contrib import admin
from django.db import models
from django.db.models import Count, F, ExpressionWrapper, FloatField, Sum
from django.utils.html import format_html
from django.urls import reverse
from django.contrib.admin import SimpleListFilter
from django.db.models import Case, When, Value, IntegerField
from django.utils import timezone
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


# ===== PRODUCT ADMIN =====

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    form = ProductForm
    list_display = [
        'image_preview', 'name', 'category_link', 'brand', 'price_display',
        'discount_badge', 'stock_status', 'available', 'rating_display', 'review_count'
    ]
    list_filter = [
        'available', 'featured', 'is_dropship',
        'category__parent', 'brand', DiscountFilter
    ]
    list_editable = ['available']
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = [
        'rating', 'review_count', 'created', 'updated',
        'search_vector_info', 'product_images_preview', 'variants_preview',
        'image_preview_large'
    ]
    search_fields = ['name', 'description', 'short_description', 'slug']
    autocomplete_fields = ['category', 'brand', 'supplier']

    fieldsets = (
        ('Basic Information', {
            'fields': ('category', 'brand', 'name', 'slug', 'short_description', 'description')
        }),
        ('Pricing & Inventory', {
            'fields': ('price', 'discount_price', 'stock', 'available')
        }),
        ('Main Image', {
            'fields': ('image', 'image_preview_large')
        }),
        ('Additional Images & Variants', {
            'fields': ('product_images_preview', 'variants_preview'),
            'classes': ('collapse',)
        }),
        ('Product Features', {
            'fields': ('featured', 'rating', 'review_count')
        }),
        ('Dropshipping', {
            'fields': (
                'is_dropship', 'supplier', 'supplier_url',
                'shipping_time', 'commission_rate', 'supplier_product_id'
            ),
            'classes': ('collapse',)
        }),
        ('Technical Information', {
            'fields': ('search_vector_info', 'created', 'updated'),
            'classes': ('collapse',)
        }),
    )

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
        """Display price with proper Money handling - BULLETPROOF VERSION"""
        # Extract raw values, no HTML at all
        if hasattr(obj.price, 'amount'):
            price_val = f"{obj.price.currency} {obj.price.amount:,.2f}"
        else:
            price_val = str(obj.price)

        if obj.discount_price:
            if hasattr(obj.discount_price, 'amount'):
                discount_val = f"{obj.discount_price.currency} {obj.discount_price.amount:,.2f}"
            else:
                discount_val = str(obj.discount_price)

            # Now safely pass plain strings to format_html
            return format_html(
                '<span style="text-decoration: line-through; color: #9ca3af;">{}</span><br>'
                '<span style="color: #dc2626; font-weight: 600;">{}</span>',
                price_val,
                discount_val
            )

        return format_html('<span style="font-weight: 600;">{}</span>', price_val)

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

        # --- FIX ---
        # Pre-format the rating number into a plain string first.
        # This avoids passing a Decimal/float directly into format_html's
        # formatter, which is causing the ValueError.
        rating_str = f"{float(obj.rating):.1f}"

        return format_html(
            '<span style="color: #fbbf24; font-size: 16px;">{}</span> <span style="color: #6b7280;">({})</span>',
            stars, rating_str  # Pass the pre-formatted string
        )
        # --- END FIX ---

    rating_display.short_description = 'Rating'


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
            models.Q(name__icontains=obj.query) |
            models.Q(description__icontains=obj.query)
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