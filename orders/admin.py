# orders/admin.py

import uuid
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.contrib.admin import SimpleListFilter
from django.db.models import Sum, F
from payment.models import Payment
from .models import Order, OrderItem


class StatusFilter(SimpleListFilter):
    title = 'Order Status'
    parameter_name = 'status'

    def lookups(self, request, model_admin):
        return [
            ('PAID', 'Paid'),
            ('PENDING', 'Pending'),
            ('CANCELLED', 'Cancelled'),
            ('PROCESSING', 'Processing'),
        ]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(status=self.value())
        return queryset


class PaymentStatusFilter(SimpleListFilter):
    title = 'Payment Status'
    parameter_name = 'payment_status'

    def lookups(self, request, model_admin):
        return [
            ('completed', 'Completed'),
            ('pending', 'Pending'),
            ('failed', 'Failed'),
        ]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(payment__status=self.value().upper())
        return queryset


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('product_link', 'price_display', 'quantity', 'total_price_display')
    fields = ('product_link', 'price_display', 'quantity', 'total_price_display')
    can_delete = False

    def product_link(self, obj):
        """Link to product detail"""
        if obj.product:
            url = reverse('admin:store_product_change', args=[obj.product.id])
            return format_html('<a href="{}">{}</a>', url, obj.product.name)
        return "-"

    product_link.short_description = 'Product'

    def price_display(self, obj):
        """Display unit price"""
        if hasattr(obj.price, 'amount'):
            return f"{obj.price.currency} {obj.price.amount:,.2f}"
        return str(obj.price)

    price_display.short_description = 'Unit Price'

    def total_price_display(self, obj):
        """Display total price for item"""
        total = obj.total_price
        if hasattr(total, 'amount'):
            return f"{total.currency} {total.amount:,.2f}"
        # Fallback for computed values
        return f"{obj.price.currency} {(obj.price.amount * obj.quantity):,.2f}"

    total_price_display.short_description = 'Total'

    def has_add_permission(self, request, obj=None):
        """Prevent adding items after order creation"""
        return False


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0
    readonly_fields = ['provider', 'status', 'amount_display', 'transaction_id',
                       'created_at', 'phone_number']
    fields = ['provider', 'status', 'amount_display', 'transaction_id',
              'phone_number', 'created_at']
    can_delete = False

    def amount_display(self, obj):
        """Display payment amount"""
        return f"{obj.amount.currency} {obj.amount.amount:,.2f}"

    amount_display.short_description = 'Amount'

    def has_add_permission(self, request, obj=None):
        """Prevent manual payment creation"""
        return False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'user_link',
        'full_name',
        'email_short',
        'city',
        'total_display',
        'status_display',
        'payment_status_display',
        'created'
    ]
    list_filter = [StatusFilter, PaymentStatusFilter, 'created', 'city', 'payment_method', 'country']
    search_fields = ['id', 'first_name', 'last_name', 'email', 'user__email',
                     'user__first_name', 'user__last_name', 'phone']
    inlines = [OrderItemInline, PaymentInline]
    readonly_fields = ['created', 'updated', 'total_cost_display', 'user_info',
                       'payment_info', 'order_summary']
    date_hierarchy = 'created'
    actions = ['mark_as_paid', 'cancel_orders']

    fieldsets = (
        ('Order Information', {
            'fields': ('id', 'user_info', 'status', 'payment_method', 'order_summary')
        }),
        ('Customer Details', {
            'fields': ('first_name', 'last_name', 'email', 'phone')
        }),
        ('Shipping Address', {
            'fields': ('address', 'city', 'state', 'postal_code', 'country')
        }),
        ('Payment', {
            'fields': ('total_cost_display', 'payment_info')
        }),
        ('Timestamps', {
            'fields': ('created', 'updated'),
            'classes': ('collapse',)
        }),
    )

    def get_queryset(self, request):
        """Optimize queryset"""
        return super().get_queryset(request).select_related(
            'user', 'payment'
        ).prefetch_related('items__product')

    def user_link(self, obj):
        """Link to user admin if authenticated"""
        if obj.user:
            url = reverse(f'admin:{obj.user._meta.app_label}_{obj.user._meta.model_name}_change',
                          args=[obj.user.id])
            return format_html('<a href="{}">{}</a>', url, obj.user.email)
        return format_html('<span style="color: #999;">Guest</span>')

    user_link.short_description = 'User'

    def full_name(self, obj):
        """Display customer full name"""
        return obj.get_full_name()

    full_name.short_description = 'Customer'

    def email_short(self, obj):
        """Truncated email for list display"""
        return obj.email[:30] + '...' if len(obj.email) > 30 else obj.email

    email_short.short_description = 'Email'

    def total_display(self, obj):
        """Display order total"""
        # Use the model's computed total_cost property
        total = obj.total_cost
        if hasattr(total, 'amount'):
            return f"{total.currency} {total.amount:,.2f}"
        return str(total)

    total_display.short_description = 'Total'
    total_display.admin_order_field = 'total'

    def status_display(self, obj):
        """Color-coded status display"""
        colors = {
            'PAID': '#28a745',
            'PENDING': '#ffc107',
            'CANCELLED': '#dc3545',
            'PROCESSING': '#17a2b8',
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display()
        )

    status_display.short_description = 'Status'

    def payment_status_display(self, obj):
        """Display payment status"""
        if hasattr(obj, 'payment') and obj.payment:
            colors = {
                'COMPLETED': '#28a745',
                'PENDING': '#ffc107',
                'FAILED': '#dc3545',
                'PROCESSING': '#17a2b8',
            }
            color = colors.get(obj.payment.status, '#6c757d')
            return format_html(
                '<span style="color: {};">{}</span>',
                color,
                obj.payment.get_status_display()
            )
        return format_html('<span style="color: #999;">No Payment</span>')

    payment_status_display.short_description = 'Payment'

    def total_cost_display(self, obj):
        """Detailed total cost display"""
        total = obj.total_cost
        if hasattr(total, 'amount'):
            return f"{total.currency} {total.amount:,.2f}"
        return str(total)

    total_cost_display.short_description = 'Total Amount'

    def user_info(self, obj):
        """Detailed user information"""
        if obj.user:
            url = reverse(f'admin:{obj.user._meta.app_label}_{obj.user._meta.model_name}_change',
                          args=[obj.user.id])
            return format_html(
                '<a href="{}">{}</a><br>'
                '<small>Email: {}</small><br>'
                '<small>Joined: {}</small>',
                url,
                obj.user.get_full_name() or obj.user.email,
                obj.user.email,
                obj.user.date_joined.strftime('%Y-%m-%d')
            )
        return format_html(
            '<strong>Guest Order</strong><br>'
            '<small>{}</small>',
            obj.email
        )

    user_info.short_description = 'User Information'

    def payment_info(self, obj):
        """Display payment information"""
        if hasattr(obj, 'payment') and obj.payment:
            payment = obj.payment
            return format_html(
                '<strong>Provider:</strong> {}<br>'
                '<strong>Status:</strong> {}<br>'
                '<strong>Amount:</strong> {} {}<br>'
                '<strong>Transaction ID:</strong> {}',
                payment.get_provider_display(),
                payment.get_status_display(),
                payment.amount.currency,
                payment.amount.amount,
                payment.transaction_id or 'N/A'
            )
        return 'No payment record'

    payment_info.short_description = 'Payment Details'

    def order_summary(self, obj):
        """Display order item summary"""
        items = obj.items.all()
        if not items:
            return 'No items'

        summary = '<table style="width:100%; border-collapse: collapse;">'
        summary += '<tr style="background: #f5f5f5;"><th>Product</th><th>Qty</th><th>Price</th><th>Total</th></tr>'

        for item in items:
            item_total = item.price.amount * item.quantity if hasattr(item.price, 'amount') else 0
            summary += f'''
            <tr style="border-bottom: 1px solid #ddd;">
                <td>{item.product.name}</td>
                <td>{item.quantity}</td>
                <td>{item.price.currency} {item.price.amount:,.2f}</td>
                <td>{item.price.currency} {item_total:,.2f}</td>
            </tr>
            '''

        total = obj.total_cost
        total_amount = total.amount if hasattr(total, 'amount') else 0
        total_currency = total.currency if hasattr(total, 'currency') else 'KES'

        summary += f'''
        <tr style="font-weight: bold; background: #f9f9f9;">
            <td colspan="3" style="text-align: right;">Total:</td>
            <td>{total_currency} {total_amount:,.2f}</td>
        </tr>
        </table>
        '''
        return format_html(summary)

    order_summary.short_description = 'Order Items'

    def mark_as_paid(self, request, queryset):
        """Bulk action to mark orders as paid"""
        updated = 0
        for order in queryset.filter(status='PENDING'):
            try:
                order.mark_as_paid('ADMIN')
                updated += 1
            except Exception as e:
                self.message_user(request, f"Error updating order {order.id}: {str(e)}", level='error')

        self.message_user(request, f"{updated} order(s) marked as paid")

    mark_as_paid.short_description = "Mark selected orders as paid"

    def cancel_orders(self, request, queryset):
        """Bulk action to cancel orders"""
        cancelled = 0
        for order in queryset.filter(status__in=['PENDING', 'PAID']):
            try:
                order.cancel_order()
                cancelled += 1
            except Exception as e:
                self.message_user(request, f"Error cancelling order {order.id}: {str(e)}", level='error')

        self.message_user(request, f"{cancelled} order(s) cancelled")

    cancel_orders.short_description = "Cancel selected orders"

    def has_delete_permission(self, request, obj=None):
        """Prevent deletion of paid orders"""
        if obj and obj.status == 'PAID':
            return False
        return super().has_delete_permission(request, obj)

    def has_change_permission(self, request, obj=None):
        """Limit editing of completed orders"""
        if obj and obj.status in ['PAID', 'CANCELLED']:
            # Allow viewing but limited editing
            return True
        return super().has_change_permission(request, obj)

    def get_readonly_fields(self, request, obj=None):
        """Make certain fields readonly for paid/cancelled orders"""
        readonly = list(self.readonly_fields)
        if obj and obj.status in ['PAID', 'CANCELLED']:
            readonly.extend(['status', 'payment_method', 'first_name', 'last_name',
                             'email', 'address', 'city', 'postal_code'])
        return readonly