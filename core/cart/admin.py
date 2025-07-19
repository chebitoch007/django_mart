from django.contrib import admin
from .models import Cart, CartItem
from django.utils.html import format_html
from django.urls import reverse
from django.contrib.admin import SimpleListFilter
from django.contrib.auth import get_user_model
from django.conf import settings

User = get_user_model()


# Custom filter for anonymous vs authenticated carts
class CartUserFilter(SimpleListFilter):
    title = 'cart owner'
    parameter_name = 'cart_owner'

    def lookups(self, request, model_admin):
        return (
            ('authenticated', 'Authenticated Users'),
            ('anonymous', 'Anonymous Users'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'authenticated':
            return queryset.filter(user__isnull=False)
        if self.value() == 'anonymous':
            return queryset.filter(user__isnull=True)


# Custom filter for CartItem admin
class CartItemUserFilter(SimpleListFilter):
    title = 'cart owner'
    parameter_name = 'cart_owner'

    def lookups(self, request, model_admin):
        return (
            ('authenticated', 'Authenticated Users'),
            ('anonymous', 'Anonymous Users'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'authenticated':
            return queryset.filter(cart__user__isnull=False)
        if self.value() == 'anonymous':
            return queryset.filter(cart__user__isnull=True)


class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0
    readonly_fields = ('product_link', 'quantity', 'total_price', 'added_at')
    fields = ('product_link', 'quantity', 'total_price', 'added_at')

    def product_link(self, instance):
        url = reverse('admin:store_product_change', args=[instance.product.id])
        return format_html('<a href="{}">{}</a>', url, instance.product)

    product_link.short_description = 'Product'

    def total_price(self, instance):
        return f"KES {instance.total_price:,.2f}"

    total_price.short_description = 'Total'


class CartAdmin(admin.ModelAdmin):
    list_display = ('id', 'owner_info', 'created_at', 'updated_at',
                    'total_items', 'total_price_value', 'session_info')
    list_filter = (CartUserFilter, 'created_at', 'updated_at')
    search_fields = ('user__username', 'user__email', 'session_key')
    readonly_fields = ('created_at', 'updated_at', 'session_info',
                       'owner_info', 'total_items', 'total_price_value')
    inlines = [CartItemInline]
    fieldsets = (
        ('Identification', {
            'fields': ('owner_info', 'session_info')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at')
        }),
        ('Cart Summary', {
            'fields': ('total_items', 'total_price_value')
        }),
    )

    def session_info(self, obj):
        if obj.session_key:
            return format_html(
                '<div class="session-info">'
                '<div><strong>Session:</strong> {}</div>'
                '<div><strong>Session Cart ID:</strong> {}</div>'
                '</div>',
                obj.session_key[:20] + '...' if len(obj.session_key) > 20 else obj.session_key,
                obj.id
            )
        return "-"

    session_info.short_description = 'Session Information'

    def owner_info(self, obj):
        if obj.user:
            # Get user model info dynamically
            app_label = obj.user._meta.app_label
            model_name = obj.user._meta.model_name

            try:
                # Try to get the change URL for the user
                url = reverse(f'admin:{app_label}_{model_name}_change', args=[obj.user.id])
                return format_html('<a href="{}">{}</a>', url, obj.user)
            except:
                # Fallback if URL doesn't exist
                return str(obj.user)
        return "Anonymous User"

    owner_info.short_description = 'Owner'

    def total_items(self, obj):
        return obj.total_items

    total_items.short_description = 'Total Items'

    def total_price_value(self, obj):
        return f"KES {obj.total_price:,.2f}"

    total_price_value.short_description = 'Total Price'


class CartItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'cart_link', 'product_link', 'quantity',
                    'unit_price', 'total_price', 'added_at')
    list_filter = (CartItemUserFilter, 'added_at')
    search_fields = ('product__name', 'cart__user__username',
                     'cart__session_key')
    readonly_fields = ('added_at', 'unit_price', 'total_price_value')
    fields = ('cart', 'product', 'quantity', 'unit_price',
              'total_price_value', 'added_at')

    def cart_link(self, obj):
        url = reverse('admin:cart_cart_change', args=[obj.cart.id])
        if obj.cart.user:
            label = f"Cart #{obj.cart.id} ({obj.cart.user})"
        else:
            label = f"Cart #{obj.cart.id} (Anonymous)"
        return format_html('<a href="{}">{}</a>', url, label)

    cart_link.short_description = 'Cart'

    def product_link(self, obj):
        url = reverse('admin:store_product_change', args=[obj.product.id])
        return format_html('<a href="{}">{}</a>', url, obj.product)

    product_link.short_description = 'Product'

    def unit_price(self, obj):
        return f"KES {obj.product.get_display_price():,.2f}"

    unit_price.short_description = 'Unit Price'

    def total_price(self, obj):
        return f"KES {obj.total_price:,.2f}"

    total_price.short_description = 'Total Price'

    def total_price_value(self, obj):
        return f"KES {obj.total_price:,.2f}"

    total_price_value.short_description = 'Total Price'


admin.site.register(Cart, CartAdmin)
admin.site.register(CartItem, CartItemAdmin)