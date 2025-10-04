from django.contrib import admin
from django.db import models
from django.db.models import Count, F, ExpressionWrapper, FloatField
from django.utils.html import format_html
from django.urls import reverse
from django.contrib.admin import SimpleListFilter
from django.db.models import Case, When, Value, IntegerField
from .forms import ProductForm
from .models import (
    Category, Product, NewsletterSubscription,
    SearchLog, ProductImage, ProductVariant, Review
)
from mptt.admin import DraggableMPTTAdmin

# Unregister first to avoid conflicts during development reloads
if admin.site.is_registered(Category):
    admin.site.unregister(Category)


@admin.register(Category)
class CategoryAdmin(DraggableMPTTAdmin):
    mptt_indent_field = "name"
    # Change to 'mptt_level' which is the actual MPTT attribute
    list_display = ('tree_actions', 'indented_title', 'is_active', 'product_count', 'mptt_level')
    list_display_links = ('indented_title',)
    list_filter = ('is_active', 'parent')
    search_fields = ('name', 'description')
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ('meta_preview',)
    fieldsets = (
        (None, {
            'fields': ('parent', 'name', 'slug')
        }),
        ('Content', {
            'fields': ('description', 'image')
        }),
        ('SEO', {
            'fields': ('meta_title', 'meta_description', 'meta_preview')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(_product_count=Count('products'))

    def product_count(self, instance):
        return instance._product_count

    product_count.admin_order_field = '_product_count'

    def meta_preview(self, instance):
        if not instance.meta_title or not instance.meta_description:
            return "Please add meta information"

        # Use the actual host in production - this is for display only
        host = "example.com"  # Replace with your actual domain in production
        return format_html(
            '<div style="border: 1px solid #ddd; padding: 10px; border-radius: 5px; max-width: 600px; background: #f9f9f9;">'
            '<div style="color: #1a0dab; font-size: 16px; margin-bottom: 5px;">{}</div>'
            '<div style="color: #006621; font-size: 14px; margin-bottom: 5px;">{}</div>'
            '<div style="color: #545454; font-size: 13px;">{}</div>'
            '</div>',
            instance.meta_title,
            f"{host}{reverse('store:product_list_by_category', args=[instance.slug])}",
            instance.meta_description
        )

    meta_preview.short_description = 'Search Preview'

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
            # Calculate discount percentage safely
            return queryset.annotate(
                discount_percent=Case(
                    When(price__gt=0, then=ExpressionWrapper(
                        (F('price') - F('discount_price')) * 100 / F('price'),
                        output_field=FloatField()
                    ),
                         default=Value(0),
                         output_field=FloatField()
                         )
                ).filter(discount_percent__gt=30))
        return queryset


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    form = ProductForm
    list_display = [
        'name', 'category_link', 'price', 'discount_price',
        'discount_percentage', 'stock', 'available', 'on_sale',
        'rating', 'review_count'
    ]
    list_filter = [
        'available', 'featured', 'is_dropship',
        'category__parent', DiscountFilter
    ]
    list_editable = ['price', 'available', 'stock']
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = [
        'rating', 'review_count', 'created', 'updated',
        'search_vector_info', 'product_images', 'variants_list'
    ]
    search_fields = ['name', 'description', 'short_description']
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'category', 'name', 'slug', 'description', 'short_description'
            )
        }),
        ('Pricing & Inventory', {
            'fields': (
                'price', 'discount_price', 'stock', 'available'
            )
        }),
        ('Media', {
            'fields': ('image', 'product_images')
        }),
        ('Product Details', {
            'fields': (
                'featured', 'rating', 'review_count', 'variants_list'
            )
        }),
        ('Dropshipping', {
            'fields': (
                'is_dropship', 'supplier', 'supplier_url',
                'shipping_time', 'commission_rate'
            ),
            'classes': ('collapse',)
        }),
        ('Technical', {
            'fields': ('search_vector_info', 'created', 'updated'),
            'classes': ('collapse',)
        }),
    )

    def category_link(self, obj):
        url = reverse('admin:store_category_change', args=[obj.category.id])
        return format_html('<a href="{}">{}</a>', url, obj.category)

    category_link.short_description = 'Category'
    category_link.admin_order_field = 'category__name'

    def discount_percentage(self, obj):
        if obj.discount_price and obj.price and obj.price > 0:
            percent = (obj.price - obj.discount_price) / obj.price * 100
            return f"{percent:.0f}%"
        return "-"

    discount_percentage.short_description = 'Discount'

    def on_sale(self, obj):
        return bool(obj.discount_price)

    on_sale.boolean = True

    def search_vector_info(self, obj):
        if obj.search_vector:
            return "Search index ready"
        return "Search index missing"

    search_vector_info.short_description = 'Search Index'

    def product_images(self, obj):
        images = obj.additional_images.all()[:5]
        html = []
        for img in images:
            html.append(
                f'<div style="float: left; margin-right: 10px; margin-bottom: 10px;">'
                f'<img src="{img.image.url}" style="max-height: 100px; max-width: 100px; border: 1px solid #ddd;" />'
                f'<div style="text-align: center;">{img.color or "No color"}</div>'
                f'</div>'
            )
        return format_html(''.join(html))

    product_images.short_description = 'Additional Images'

    def variants_list(self, obj):
        variants = obj.variants.all()[:10]
        if not variants:
            return "No variants"

        html = ['<ul>']
        for v in variants:
            html.append(
                f'<li>{v.color} {v.size} - KES {v.price} ({v.quantity} in stock)</li>'
            )
        html.append('</ul>')
        return format_html(''.join(html))

    variants_list.short_description = 'Product Variants'


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


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = [
        'product_link', 'user', 'rating_stars', 'title',
        'approved', 'created'
    ]
    list_filter = ['rating', 'approved', ReviewStatusFilter]
    search_fields = ['product__name', 'user__username', 'title', 'comment']
    list_editable = ['approved']
    readonly_fields = ['created', 'updated', 'rating_stars_display']
    fieldsets = (
        ('Review Content', {
            'fields': ('product', 'user', 'rating_stars_display', 'title', 'comment')
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
        return self.rating_stars(obj)

    rating_stars_display.short_description = 'Rating'


@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    list_display = ['product_link', 'image_preview', 'color', 'is_featured']
    list_filter = ['is_featured', 'color']
    search_fields = ['product__name', 'color']
    list_editable = ['is_featured', 'color']
    readonly_fields = ['image_preview_large']

    def product_link(self, obj):
        url = reverse('admin:store_product_change', args=[obj.product.id])
        return format_html('<a href="{}">{}</a>', url, obj.product)

    product_link.short_description = 'Product'

    def image_preview(self, obj):
        return format_html(
            '<img src="{}" style="max-height: 50px; max-width: 50px;" />',
            obj.image.url
        )

    image_preview.short_description = 'Preview'

    def image_preview_large(self, obj):
        return format_html(
            '<img src="{}" style="max-height: 300px; max-width: 300px;" />',
            obj.image.url
        )

    image_preview_large.short_description = 'Image Preview'


@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display = [
        'product_link', 'color', 'size', 'price',
        'quantity', 'stock_status'
    ]
    list_filter = ['color', 'product__category']
    search_fields = ['product__name', 'color', 'size']
    list_editable = ['price', 'quantity', 'color', 'size']
    readonly_fields = ['product_link']

    def product_link(self, obj):
        url = reverse('admin:store_product_change', args=[obj.product.id])
        return format_html('<a href="{}">{}</a>', url, obj.product)

    product_link.short_description = 'Product'

    def stock_status(self, obj):
        if obj.quantity > 10:
            return "In Stock"
        elif obj.quantity > 0:
            return f"Low Stock ({obj.quantity})"
        return "Out of Stock"

    stock_status.short_description = 'Status'

    def save_model(self, request, obj, form, change):
        # Update main product stock when variants change
        super().save_model(request, obj, form, change)
        obj.product.stock = obj.product.variants.aggregate(
            total_stock=models.Sum('quantity')
        )['total_stock'] or 0
        obj.product.save()


@admin.register(SearchLog)
class SearchLogAdmin(admin.ModelAdmin):
    list_display = ['query', 'created_at', 'ip_address', 'result_count']
    list_filter = ['created_at']
    search_fields = ['query', 'ip_address']
    readonly_fields = ['created_at', 'ip_address']
    date_hierarchy = 'created_at'

    def result_count(self, obj):
        from .models import Product
        return Product.objects.search(obj.query).count()
    result_count.short_description = 'Results'


@admin.register(NewsletterSubscription)
class NewsletterSubscriptionAdmin(admin.ModelAdmin):
    list_display = [
        'email', 'confirmed', 'unsubscribed',
        'created_at', 'status'
    ]
    search_fields = ['email']
    list_filter = ['confirmed', 'unsubscribed']
    readonly_fields = [
        'confirmation_token', 'confirmation_sent',
        'confirmed_at', 'created_at', 'ip_address',
        'source_url', 'unsubscribe_token'
    ]

    def status(self, obj):
        if obj.unsubscribed:
            return "Unsubscribed"
        if obj.confirmed:
            return "Subscribed"
        return "Pending Confirmation"

    status.short_description = 'Status'