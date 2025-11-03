# orders/admin.py - ENHANCED VERSION

import uuid
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.contrib.admin import SimpleListFilter
from django.db.models import Sum, F, Count, Q
from django.utils.safestring import mark_safe
from payment.models import Payment
from .models import Order, OrderItem


class StatusFilter(SimpleListFilter):
    """Filter orders by status"""
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
    """Filter orders by payment status"""
    title = 'Payment Status'
    parameter_name = 'payment_status'

    def lookups(self, request, model_admin):
        return [
            ('COMPLETED', 'Completed'),
            ('PENDING', 'Pending'),
            ('FAILED', 'Failed'),
            ('PROCESSING', 'Processing'),
        ]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(payment__status=self.value())
        return queryset


class DeliveryInstructionsFilter(SimpleListFilter):
    """Filter orders with delivery instructions"""
    title = 'Delivery Instructions'
    parameter_name = 'has_delivery_instructions'

    def lookups(self, request, model_admin):
        return [
            ('yes', 'Has Instructions'),
            ('no', 'No Instructions'),
        ]

    def queryset(self, request, queryset):
        if self.value() == 'yes':
            return queryset.exclude(Q(delivery_instructions='') | Q(delivery_instructions__isnull=True))
        elif self.value() == 'no':
            return queryset.filter(Q(delivery_instructions='') | Q(delivery_instructions__isnull=True))
        return queryset


class BillingAddressFilter(SimpleListFilter):
    """Filter by billing address preference"""
    title = 'Billing Address'
    parameter_name = 'billing_preference'

    def lookups(self, request, model_admin):
        return [
            ('same', 'Same as Shipping'),
            ('different', 'Different Address'),
        ]

    def queryset(self, request, queryset):
        if self.value() == 'same':
            return queryset.filter(billing_same_as_shipping=True)
        elif self.value() == 'different':
            return queryset.filter(billing_same_as_shipping=False)
        return queryset


class OrderItemInline(admin.TabularInline):
    """Inline display of order items"""
    model = OrderItem
    extra = 0
    readonly_fields = ('product_link', 'price_display', 'quantity', 'total_price_display')
    fields = ('product_link', 'price_display', 'quantity', 'total_price_display')
    can_delete = False

    def product_link(self, obj):
        """Link to product detail"""
        if obj.product:
            url = reverse('admin:store_product_change', args=[obj.product.id])
            return format_html(
                '<a href="{}" target="_blank">{}</a>',
                url,
                obj.product.name
            )
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
    """Inline display of payment information"""
    model = Payment
    extra = 0
    readonly_fields = [
        'provider', 'status', 'amount_display', 'transaction_id',
        'created_at', 'phone_number', 'payment_link'
    ]
    fields = [
        'provider', 'status', 'amount_display', 'transaction_id',
        'phone_number', 'created_at', 'payment_link'
    ]
    can_delete = False

    def amount_display(self, obj):
        """Display payment amount"""
        return f"{obj.amount.currency} {obj.amount.amount:,.2f}"

    amount_display.short_description = 'Amount'

    def payment_link(self, obj):
        """Link to payment admin"""
        if obj.id:
            url = reverse('admin:payment_payment_change', args=[obj.id])
            return format_html(
                '<a href="{}" target="_blank">View Payment Details</a>',
                url
            )
        return '-'

    payment_link.short_description = 'Details'

    def has_add_permission(self, request, obj=None):
        """Prevent manual payment creation"""
        return False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    """Enhanced admin interface for Order model"""

    list_display = [
        'id',
        'user_link',
        'full_name',
        'email_short',
        'phone_short',
        'city',
        'country',
        'total_display',
        'status_display',
        'payment_status_display',
        'delivery_note_indicator',
        'created',
    ]

    list_filter = [
        StatusFilter,
        PaymentStatusFilter,
        DeliveryInstructionsFilter,
        BillingAddressFilter,
        'created',
        'city',
        'country',
        'payment_method',
    ]

    search_fields = [
        'id',
        'first_name',
        'last_name',
        'email',
        'user__email',
        'user__first_name',
        'user__last_name',
        'phone',
        'address',
        'city',
        'postal_code',
    ]

    inlines = [OrderItemInline, PaymentInline]

    readonly_fields = [
        'created',
        'updated',
        'total_cost_display',
        'user_info',
        'payment_info',
        'order_summary',
        'shipping_details_display',
        'delivery_instructions_display',
    ]

    date_hierarchy = 'created'

    actions = ['mark_as_paid', 'cancel_orders', 'export_shipping_labels']

    fieldsets = (
        ('Order Information', {
            'fields': (
                'id',
                'user_info',
                'status',
                'payment_method',
                'order_summary'
            )
        }),
        ('Customer Details', {
            'fields': (
                'first_name',
                'last_name',
                'email',
                'phone'
            ),
            'classes': ('wide',)
        }),
        ('Shipping Address', {
            'fields': (
                'address',
                'city',
                'state',
                'postal_code',
                'country',
                'shipping_details_display',
            ),
            'classes': ('wide',)
        }),
        ('Delivery Information', {
            'fields': (
                'delivery_instructions',
                'delivery_instructions_display',
            ),
            'classes': ('wide',),
            'description': 'Special delivery instructions from customer'
        }),
        ('Billing Information', {
            'fields': (
                'billing_same_as_shipping',
            ),
            'classes': ('collapse',)
        }),
        ('Payment', {
            'fields': (
                'total_cost_display',
                'payment_info'
            )
        }),
        ('Timestamps', {
            'fields': ('created', 'updated'),
            'classes': ('collapse',)
        }),
    )

    def get_queryset(self, request):
        """Optimize queryset with related data"""
        return super().get_queryset(request).select_related(
            'user', 'payment'
        ).prefetch_related('items__product').annotate(
            items_count=Count('items')
        )

    def user_link(self, obj):
        """Link to user admin if authenticated"""
        if obj.user:
            url = reverse(
                f'admin:{obj.user._meta.app_label}_{obj.user._meta.model_name}_change',
                args=[obj.user.id]
            )
            return format_html(
                '<a href="{}" target="_blank">{}</a>',
                url,
                obj.user.email
            )
        return format_html('<span style="color: #999;">Guest</span>')

    user_link.short_description = 'User'
    user_link.admin_order_field = 'user__email'

    def full_name(self, obj):
        """Display customer full name"""
        return obj.get_full_name()

    full_name.short_description = 'Customer'
    full_name.admin_order_field = 'first_name'

    def email_short(self, obj):
        """Truncated email for list display"""
        email = obj.email
        return email[:30] + '...' if len(email) > 30 else email

    email_short.short_description = 'Email'
    email_short.admin_order_field = 'email'

    def phone_short(self, obj):
        """Display phone number"""
        if obj.phone:
            # Format phone for display (e.g., +254712345678 -> +254 712 345 678)
            phone = str(obj.phone)
            if len(phone) > 10:
                return f"{phone[:4]} {phone[4:7]} {phone[7:10]} {phone[10:]}"
            return phone
        return '-'

    phone_short.short_description = 'Phone'
    phone_short.admin_order_field = 'phone'

    def total_display(self, obj):
        """Display order total with currency"""
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
        icons = {
            'PAID': '✓',
            'PENDING': '⏳',
            'CANCELLED': '✗',
            'PROCESSING': '⚙',
        }
        color = colors.get(obj.status, '#6c757d')
        icon = icons.get(obj.status, '•')

        return format_html(
            '<span style="color: {}; font-weight: bold;">{} {}</span>',
            color,
            icon,
            obj.get_status_display()
        )

    status_display.short_description = 'Status'
    status_display.admin_order_field = 'status'

    def payment_status_display(self, obj):
        """Display payment status with color coding"""
        if hasattr(obj, 'payment') and obj.payment:
            colors = {
                'COMPLETED': '#28a745',
                'PENDING': '#ffc107',
                'FAILED': '#dc3545',
                'PROCESSING': '#17a2b8',
            }
            color = colors.get(obj.payment.status, '#6c757d')
            return format_html(
                '<span style="color: {}; font-weight: 600;">{}</span>',
                color,
                obj.payment.get_status_display()
            )
        return format_html('<span style="color: #999;">No Payment</span>')

    payment_status_display.short_description = 'Payment'

    def delivery_note_indicator(self, obj):
        """Visual indicator for delivery instructions"""
        if obj.delivery_instructions:
            return format_html(
                '<span style="color: #17a2b8;" title="{}">📝 Yes</span>',
                obj.delivery_instructions[:50] + ('...' if len(obj.delivery_instructions) > 50 else '')
            )
        return format_html('<span style="color: #ccc;">-</span>')

    delivery_note_indicator.short_description = 'Delivery Note'

    def total_cost_display(self, obj):
        """Detailed total cost display"""
        total = obj.total_cost
        if hasattr(total, 'amount'):
            return format_html(
                '<div style="font-size: 1.2em; font-weight: bold; color: #28a745;">'
                '{} {:,.2f}'
                '</div>',
                total.currency,
                total.amount
            )
        return str(total)

    total_cost_display.short_description = 'Total Amount'

    def user_info(self, obj):
        """Detailed user information card"""
        if obj.user:
            url = reverse(
                f'admin:{obj.user._meta.app_label}_{obj.user._meta.model_name}_change',
                args=[obj.user.id]
            )
            return format_html(
                '<div style="padding: 10px; background: #f8f9fa; border-radius: 5px;">'
                '<a href="{}" target="_blank" style="font-weight: bold; font-size: 1.1em;">{}</a><br>'
                '<small>📧 Email: {}</small><br>'
                '<small>📅 Joined: {}</small><br>'
                '<small>📦 Total Orders: {}</small>'
                '</div>',
                url,
                obj.user.get_full_name() or obj.user.email,
                obj.user.email,
                obj.user.date_joined.strftime('%Y-%m-%d'),
                Order.objects.filter(user=obj.user).count()
            )
        return format_html(
            '<div style="padding: 10px; background: #fff3cd; border-radius: 5px;">'
            '<strong>👤 Guest Order</strong><br>'
            '<small>📧 {}</small>'
            '</div>',
            obj.email
        )

    user_info.short_description = 'User Information'

    def shipping_details_display(self, obj):
        """Enhanced shipping address display"""
        return format_html(
            '<div style="padding: 10px; background: #f8f9fa; border-radius: 5px; line-height: 1.8;">'
            '<strong style="color: #495057;">📍 Complete Shipping Address:</strong><br>'
            '<span style="font-size: 1.05em;">{}</span><br>'
            '{}'
            '<span>{}, {} {}</span><br>'
            '<span>{}</span><br>'
            '<span style="font-weight: 600;">📞 Phone: {}</span>'
            '</div>',
            obj.address,
            f'<span>{obj.state}, </span><br>' if obj.state else '',
            obj.city,
            obj.postal_code if obj.postal_code else '',
            '',
            obj.country.name if obj.country else 'N/A',
            obj.phone if obj.phone else 'N/A'
        )

    shipping_details_display.short_description = 'Full Shipping Address'

    def delivery_instructions_display(self, obj):
        """Display delivery instructions in detail view"""
        if obj.delivery_instructions:
            return format_html(
                '<div style="padding: 12px; background: #e7f3ff; border-left: 4px solid #2196F3; border-radius: 4px;">'
                '<strong style="color: #1976D2;">📝 Delivery Instructions:</strong><br>'
                '<p style="margin: 8px 0 0 0; line-height: 1.6;">{}</p>'
                '</div>',
                obj.delivery_instructions
            )
        return format_html(
            '<div style="padding: 12px; background: #f5f5f5; border-radius: 4px; color: #999;">'
            'No special delivery instructions provided'
            '</div>'
        )

    delivery_instructions_display.short_description = 'Delivery Instructions'

    def payment_info(self, obj):
        """Display payment information card"""
        if hasattr(obj, 'payment') and obj.payment:
            payment = obj.payment
            status_colors = {
                'COMPLETED': '#28a745',
                'PENDING': '#ffc107',
                'FAILED': '#dc3545',
                'PROCESSING': '#17a2b8',
            }
            status_color = status_colors.get(payment.status, '#6c757d')

            return format_html(
                '<div style="padding: 10px; background: #f8f9fa; border-radius: 5px;">'
                '<strong style="font-size: 1.05em;">💳 Payment Details</strong><br><br>'
                '<strong>Provider:</strong> {}<br>'
                '<strong>Status:</strong> <span style="color: {}; font-weight: bold;">{}</span><br>'
                '<strong>Amount:</strong> {} {:,.2f}<br>'
                '<strong>Transaction ID:</strong> {}<br>'
                '<strong>Phone:</strong> {}<br>'
                '<strong>Date:</strong> {}'
                '</div>',
                payment.get_provider_display(),
                status_color,
                payment.get_status_display(),
                payment.amount.currency,
                payment.amount.amount,
                payment.transaction_id or 'N/A',
                payment.phone_number or 'N/A',
                payment.created_at.strftime('%Y-%m-%d %H:%M')
            )
        return format_html(
            '<div style="padding: 10px; background: #fff3cd; border-radius: 5px;">'
            '⚠️ No payment record found'
            '</div>'
        )

    payment_info.short_description = 'Payment Details'

    def order_summary(self, obj):
        """Display order item summary table"""
        items = obj.items.all()
        if not items:
            return format_html(
                '<div style="padding: 10px; color: #999;">No items in this order</div>'
            )

        summary = '<div style="padding: 10px; background: #fff; border-radius: 5px;">'
        summary += '<table style="width:100%; border-collapse: collapse; font-size: 0.95em;">'
        summary += '''
        <thead>
            <tr style="background: #e9ecef; border-bottom: 2px solid #dee2e6;">
                <th style="padding: 10px; text-align: left;">Product</th>
                <th style="padding: 10px; text-align: center;">Qty</th>
                <th style="padding: 10px; text-align: right;">Unit Price</th>
                <th style="padding: 10px; text-align: right;">Total</th>
            </tr>
        </thead>
        <tbody>
        '''

        for item in items:
            item_total = item.price.amount * item.quantity if hasattr(item.price, 'amount') else 0
            summary += f'''
            <tr style="border-bottom: 1px solid #e9ecef;">
                <td style="padding: 10px;">{item.product.name}</td>
                <td style="padding: 10px; text-align: center;">{item.quantity}</td>
                <td style="padding: 10px; text-align: right;">{item.price.currency} {item.price.amount:,.2f}</td>
                <td style="padding: 10px; text-align: right; font-weight: 600;">{item.price.currency} {item_total:,.2f}</td>
            </tr>
            '''

        total = obj.total_cost
        total_amount = total.amount if hasattr(total, 'amount') else 0
        total_currency = total.currency if hasattr(total, 'currency') else 'KES'

        summary += f'''
        </tbody>
        <tfoot>
            <tr style="font-weight: bold; background: #f8f9fa; font-size: 1.1em;">
                <td colspan="3" style="padding: 12px; text-align: right;">Grand Total:</td>
                <td style="padding: 12px; text-align: right; color: #28a745;">{total_currency} {total_amount:,.2f}</td>
            </tr>
        </tfoot>
        </table>
        </div>
        '''

        # Add billing info
        if not obj.billing_same_as_shipping:
            summary += '''
            <div style="margin-top: 10px; padding: 8px; background: #fff3cd; border-radius: 4px; font-size: 0.9em;">
                ⚠️ Customer requested different billing address
            </div>
            '''

        return mark_safe(summary)

    order_summary.short_description = 'Order Items & Total'

    # Admin Actions
    def mark_as_paid(self, request, queryset):
        """Bulk action to mark orders as paid"""
        updated = 0
        errors = []

        for order in queryset.filter(status='PENDING'):
            try:
                order.mark_as_paid('ADMIN')
                updated += 1
            except Exception as e:
                errors.append(f"Order {order.id}: {str(e)}")

        if updated:
            self.message_user(
                request,
                f"✓ Successfully marked {updated} order(s) as paid",
                level='success'
            )

        if errors:
            self.message_user(
                request,
                f"✗ Errors: {'; '.join(errors)}",
                level='error'
            )

    mark_as_paid.short_description = "✓ Mark selected orders as paid"

    def cancel_orders(self, request, queryset):
        """Bulk action to cancel orders"""
        cancelled = 0
        errors = []

        for order in queryset.filter(status__in=['PENDING', 'PAID']):
            try:
                order.cancel_order()
                cancelled += 1
            except Exception as e:
                errors.append(f"Order {order.id}: {str(e)}")

        if cancelled:
            self.message_user(
                request,
                f"✓ Successfully cancelled {cancelled} order(s)",
                level='success'
            )

        if errors:
            self.message_user(
                request,
                f"✗ Errors: {'; '.join(errors)}",
                level='error'
            )

    cancel_orders.short_description = "✗ Cancel selected orders"

    def export_shipping_labels(self, request, queryset):
        """Export shipping labels for selected orders"""
        # This is a placeholder - implement actual export logic
        orders_with_instructions = queryset.filter(
            delivery_instructions__isnull=False
        ).exclude(delivery_instructions='')

        count = orders_with_instructions.count()

        self.message_user(
            request,
            f"📦 Selected {queryset.count()} order(s). "
            f"{count} have delivery instructions.",
            level='info'
        )

    export_shipping_labels.short_description = "📦 Export shipping labels"

    # Permissions
    def has_delete_permission(self, request, obj=None):
        """Prevent deletion of paid orders"""
        if obj and obj.status == 'PAID':
            return False
        return super().has_delete_permission(request, obj)

    def has_change_permission(self, request, obj=None):
        """Allow viewing but limit editing of completed orders"""
        return True

    def get_readonly_fields(self, request, obj=None):
        """Make certain fields readonly for paid/cancelled orders"""
        readonly = list(self.readonly_fields)

        if obj and obj.status in ['PAID', 'CANCELLED']:
            # Lock down critical fields for completed orders
            readonly.extend([
                'status', 'payment_method', 'first_name', 'last_name',
                'email', 'phone', 'address', 'city', 'postal_code',
                'state', 'country', 'billing_same_as_shipping'
            ])

        return readonly


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    """Admin interface for OrderItem model"""
    list_display = ['id', 'order_link', 'product_link', 'quantity', 'price_display', 'total_display']
    list_filter = ['order__status', 'order__created']
    search_fields = ['order__id', 'product__name']
    readonly_fields = ['order', 'product', 'price', 'quantity']

    def order_link(self, obj):
        """Link to order"""
        url = reverse('admin:orders_order_change', args=[obj.order.id])
        return format_html('<a href="{}" target="_blank">Order #{}</a>', url, obj.order.id)

    order_link.short_description = 'Order'

    def product_link(self, obj):
        """Link to product"""
        url = reverse('admin:store_product_change', args=[obj.product.id])
        return format_html('<a href="{}" target="_blank">{}</a>', url, obj.product.name)

    product_link.short_description = 'Product'

    def price_display(self, obj):
        """Display price"""
        return f"{obj.price.currency} {obj.price.amount:,.2f}"

    price_display.short_description = 'Unit Price'

    def total_display(self, obj):
        """Display total"""
        total = obj.total_price
        return f"{total.currency} {total.amount:,.2f}"

    total_display.short_description = 'Total Price'

    def has_add_permission(self, request):
        """Prevent manual creation"""
        return False

    def has_delete_permission(self, request, obj=None):
        """Prevent deletion"""
        return False