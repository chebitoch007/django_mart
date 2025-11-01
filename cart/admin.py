# cart/admin.py

from django.contrib import admin
from .models import Cart, CartItem
from django.utils.html import format_html
from django.urls import reverse
from django.contrib.admin import SimpleListFilter
from django.contrib.auth import get_user_model

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
    readonly_fields = ('product_link', 'quantity', 'total_price_display', 'added_at')
    fields = ('product_link', 'quantity', 'total_price_display', 'added_at')
    can_delete = True

    def product_link(self, instance):
        if instance.product:
            url = reverse('admin:store_product_change', args=[instance.product.id])
            return format_html('<a href="{}">{}</a>', url, instance.product)
        return "-"

    product_link.short_description = 'Product'

    def total_price_display(self, instance):
        """Display total price for item"""
        total = instance.total_price
        if hasattr(total, 'amount'):
            return f"{total.currency} {total.amount:,.2f}"
        return f"KES {float(total):,.2f}"

    total_price_display.short_description = 'Total'

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ('id', 'owner_info', 'created_at', 'updated_at',
                    'total_items_display', 'total_price_display', 'session_info_short')
    list_filter = (CartUserFilter, 'created_at', 'updated_at')
    search_fields = ('user__username', 'user__email', 'user__first_name', 'user__last_name', 'session_key')
    readonly_fields = ('created_at', 'updated_at', 'session_info',
                       'owner_info', 'total_items_display', 'total_price_display')
    inlines = [CartItemInline]
    date_hierarchy = 'created_at'

    fieldsets = (
        ('Identification', {
            'fields': ('owner_info', 'session_info')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at')
        }),
        ('Cart Summary', {
            'fields': ('total_items_display', 'total_price_display')
        }),
    )

    def get_queryset(self, request):
        """Optimize queryset with select_related"""
        return super().get_queryset(request).select_related('user').prefetch_related('items__product')

    def session_info(self, obj):
        """Detailed session info for detail page"""
        if obj.session_key:
            return format_html(
                '<div class="session-info">'
                '<div><strong>Session:</strong> {}</div>'
                '<div><strong>Cart ID:</strong> {}</div>'
                '</div>',
                obj.session_key[:20] + '...' if len(obj.session_key) > 20 else obj.session_key,
                obj.id
            )
        return "-"

    session_info.short_description = 'Session Information'

    def session_info_short(self, obj):
        """Short session info for list display"""
        if obj.session_key:
            return obj.session_key[:15] + '...'
        return "-"

    session_info_short.short_description = 'Session'

    def owner_info(self, obj):
        """Display owner with link to user admin"""
        if obj.user:
            app_label = obj.user._meta.app_label
            model_name = obj.user._meta.model_name

            try:
                url = reverse(f'admin:{app_label}_{model_name}_change', args=[obj.user.id])
                return format_html(
                    '<a href="{}">{}</a><br><small>{}</small>',
                    url,
                    obj.user.get_full_name() or obj.user.email,
                    obj.user.email
                )
            except Exception:
                return str(obj.user)
        return format_html('<span style="color: #999;">Anonymous User</span>')

    owner_info.short_description = 'Owner'

    def total_items_display(self, obj):
        """Display total items count"""
        return obj.total_items

    total_items_display.short_description = 'Total Items'

    def total_price_display(self, obj):
        """Display formatted total price"""
        total = obj.total_price
        if hasattr(total, 'amount'):
            return f"{total.currency} {total.amount:,.2f}"
        return f"KES {float(total):,.2f}"

    total_price_display.short_description = 'Total Price'

    def has_add_permission(self, request):
        """Prevent manual cart creation"""
        return False


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'cart_link', 'product_link', 'quantity',
                    'unit_price_display', 'total_price_display', 'added_at')
    list_filter = (CartItemUserFilter, 'added_at')
    search_fields = ('product__name', 'cart__user__username', 'cart__user__email',
                     'cart__session_key')
    readonly_fields = ('added_at', 'unit_price_display', 'total_price_display')
    fields = ('cart', 'product', 'quantity', 'unit_price_display',
              'total_price_display', 'added_at')
    date_hierarchy = 'added_at'
    autocomplete_fields = ['product']
    raw_id_fields = ['cart']

    def get_queryset(self, request):
        """Optimize queryset"""
        return super().get_queryset(request).select_related('cart__user', 'product')

    def cart_link(self, obj):
        """Link to cart detail"""
        url = reverse('admin:cart_cart_change', args=[obj.cart.id])
        if obj.cart.user:
            label = f"Cart #{obj.cart.id} ({obj.cart.user.email})"
        else:
            session_short = obj.cart.session_key[:10] + '...' if obj.cart.session_key else 'N/A'
            label = f"Cart #{obj.cart.id} ({session_short})"
        return format_html('<a href="{}">{}</a>', url, label)

    cart_link.short_description = 'Cart'

    def product_link(self, obj):
        """Link to product detail"""
        if obj.product:
            url = reverse('admin:store_product_change', args=[obj.product.id])
            return format_html('<a href="{}">{}</a>', url, obj.product)
        return "-"

    product_link.short_description = 'Product'

    def unit_price_display(self, obj):
        """Display unit price"""
        if obj.product:
            price = obj.product.get_display_price()
            if hasattr(price, 'amount'):
                return f"{price.currency} {price.amount:,.2f}"
            return f"KES {float(price):,.2f}"
        return "-"

    unit_price_display.short_description = 'Unit Price'

    def total_price_display(self, obj):
        """Display total price"""
        total = obj.total_price
        if hasattr(total, 'amount'):
            return f"{total.currency} {total.amount:,.2f}"
        return f"KES {float(total):,.2f}"

    total_price_display.short_description = 'Total Price'

    def has_add_permission(self, request):
        """Prevent manual cart item creation"""
        return False