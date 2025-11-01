# payment/admin.py

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.contrib.admin import SimpleListFilter
from django.utils import timezone
from datetime import timedelta
from .models import Payment


class PaymentProviderFilter(SimpleListFilter):
    title = 'Payment Provider'
    parameter_name = 'provider'

    def lookups(self, request, model_admin):
        return Payment.PROVIDER_CHOICES

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(provider=self.value())
        return queryset


class PaymentStatusFilter(SimpleListFilter):
    title = 'Payment Status'
    parameter_name = 'status'

    def lookups(self, request, model_admin):
        return [
            ('COMPLETED', 'Completed'),
            ('PENDING', 'Pending'),
            ('PROCESSING', 'Processing'),
            ('FAILED', 'Failed'),
        ]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(status=self.value())
        return queryset


class FailureTypeFilter(SimpleListFilter):
    title = 'Failure Type'
    parameter_name = 'failure_type'

    def lookups(self, request, model_admin):
        return [
            ('TEMPORARY', 'Temporary'),
            ('USER_CANCELLED', 'User Cancelled'),
            ('PERMANENT', 'Permanent'),
            ('TIMEOUT', 'Timeout'),
        ]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(failure_type=self.value())
        return queryset


class ProcessingTimeFilter(SimpleListFilter):
    title = 'Processing Time'
    parameter_name = 'processing_time'

    def lookups(self, request, model_admin):
        return [
            ('fast', 'Under 5 minutes'),
            ('normal', '5-15 minutes'),
            ('slow', '15-30 minutes'),
            ('timeout', 'Over 30 minutes'),
        ]

    def queryset(self, request, queryset):
        now = timezone.now()
        if self.value() == 'fast':
            cutoff = now - timedelta(minutes=5)
            return queryset.filter(created_at__gte=cutoff, status='PROCESSING')
        elif self.value() == 'normal':
            start = now - timedelta(minutes=15)
            end = now - timedelta(minutes=5)
            return queryset.filter(created_at__range=[start, end], status='PROCESSING')
        elif self.value() == 'slow':
            start = now - timedelta(minutes=30)
            end = now - timedelta(minutes=15)
            return queryset.filter(created_at__range=[start, end], status='PROCESSING')
        elif self.value() == 'timeout':
            cutoff = now - timedelta(minutes=30)
            return queryset.filter(created_at__lte=cutoff, status='PROCESSING')
        return queryset


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'order_link',
        'provider_display',
        'status_display',
        'amount_display',
        'transaction_id_short',
        'phone_number',
        'retry_count',
        'created_at',
        'processing_time'
    )
    list_filter = (
        PaymentStatusFilter,
        PaymentProviderFilter,
        FailureTypeFilter,
        ProcessingTimeFilter,
        'created_at'
    )
    search_fields = (
        'order__id',
        'transaction_id',
        'phone_number',
        'checkout_request_id',
        'order__email',
        'order__user__email'
    )
    readonly_fields = (
        'created_at',
        'raw_response_display',
        'order_info',
        'payment_details',
        'retry_info',
        'webhook_info'
    )
    date_hierarchy = 'created_at'
    actions = ['mark_as_completed', 'mark_as_failed', 'retry_failed_payments']

    fieldsets = (
        ('Payment Information', {
            'fields': ('order_info', 'provider', 'status', 'amount')
        }),
        ('Transaction Details', {
            'fields': (
                'transaction_id',
                'checkout_request_id',
                'result_code',
                'result_description'
            )
        }),
        ('Contact Information', {
            'fields': ('phone_number', 'paypal_email')
        }),
        ('Currency Information', {
            'fields': ('original_amount', 'converted_amount', 'exchange_rate'),
            'classes': ('collapse',)
        }),
        ('Failure Information', {
            'fields': ('failure_type', 'retry_info'),
            'classes': ('collapse',)
        }),
        ('Webhook Data', {
            'fields': ('webhook_info', 'raw_response_display'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'payment_details')
        }),
    )

    def get_queryset(self, request):
        """Optimize queryset"""
        return super().get_queryset(request).select_related(
            'order__user'
        ).prefetch_related('order__items')

    def order_link(self, obj):
        """Link to order detail"""
        url = reverse('admin:orders_order_change', args=[obj.order.id])
        return format_html('<a href="{}">Order #{}</a>', url, obj.order.id)

    order_link.short_description = 'Order'
    order_link.admin_order_field = 'order'

    def provider_display(self, obj):
        """Display provider with icon"""
        icons = {
            'MPESA': '📱',
            'PAYPAL': '💳',
        }
        icon = icons.get(obj.provider, '💰')
        return format_html('{} {}', icon, obj.get_provider_display())

    provider_display.short_description = 'Provider'

    def status_display(self, obj):
        """Color-coded status display"""
        colors = {
            'COMPLETED': '#28a745',
            'PENDING': '#ffc107',
            'PROCESSING': '#17a2b8',
            'FAILED': '#dc3545',
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display()
        )

    status_display.short_description = 'Status'
    status_display.admin_order_field = 'status'

    def amount_display(self, obj):
        """Display payment amount"""
        return f"{obj.amount.currency} {obj.amount.amount:,.2f}"

    amount_display.short_description = 'Amount'
    amount_display.admin_order_field = 'amount'

    def transaction_id_short(self, obj):
        """Shortened transaction ID"""
        if obj.transaction_id:
            return obj.transaction_id[:20] + '...' if len(obj.transaction_id) > 20 else obj.transaction_id
        return '-'

    transaction_id_short.short_description = 'Transaction ID'

    def processing_time(self, obj):
        """Show how long payment has been processing"""
        if obj.status == 'PROCESSING':
            delta = timezone.now() - obj.created_at
            minutes = int(delta.total_seconds() / 60)

            if minutes < 5:
                color = 'green'
            elif minutes < 15:
                color = 'orange'
            else:
                color = 'red'

            return format_html(
                '<span style="color: {};">{} min</span>',
                color,
                minutes
            )
        return '-'

    processing_time.short_description = 'Processing Time'

    def order_info(self, obj):
        """Detailed order information"""
        order = obj.order
        url = reverse('admin:orders_order_change', args=[order.id])

        return format_html(
            '<strong>Order #{}</strong><br>'
            '<a href="{}">View Order</a><br>'
            '<small>Customer: {}</small><br>'
            '<small>Email: {}</small><br>'
            '<small>Total: {} {}</small><br>'
            '<small>Status: {}</small>',
            order.id,
            url,
            order.get_full_name(),
            order.email,
            order.total.currency,
            order.total_cost.amount,
            order.get_status_display()
        )

    order_info.short_description = 'Order Information'

    def payment_details(self, obj):
        """Comprehensive payment details"""
        details = f'<strong>Payment ID:</strong> {obj.id}<br>'
        details += f'<strong>Provider:</strong> {obj.get_provider_display()}<br>'
        details += f'<strong>Status:</strong> {obj.get_status_display()}<br>'
        details += f'<strong>Amount:</strong> {obj.amount.currency} {obj.amount.amount:,.2f}<br>'

        if obj.transaction_id:
            details += f'<strong>Transaction ID:</strong> {obj.transaction_id}<br>'

        if obj.checkout_request_id:
            details += f'<strong>Checkout Request ID:</strong> {obj.checkout_request_id}<br>'

        if obj.result_code:
            details += f'<strong>Result Code:</strong> {obj.result_code}<br>'

        if obj.result_description:
            details += f'<strong>Result:</strong> {obj.result_description}<br>'

        if obj.phone_number:
            details += f'<strong>Phone:</strong> {obj.phone_number}<br>'

        if obj.original_amount and obj.converted_amount:
            details += f'<strong>Original:</strong> {obj.original_amount.currency} {obj.original_amount.amount}<br>'
            details += f'<strong>Converted:</strong> {obj.converted_amount.currency} {obj.converted_amount.amount}<br>'
            if obj.exchange_rate:
                details += f'<strong>Rate:</strong> {obj.exchange_rate}<br>'

        return format_html(details)

    payment_details.short_description = 'Payment Details'

    def retry_info(self, obj):
        """Retry information"""
        if obj.retry_count > 0:
            info = f'<strong>Retries:</strong> {obj.retry_count}<br>'
            if obj.last_retry_at:
                info += f'<strong>Last Retry:</strong> {obj.last_retry_at.strftime("%Y-%m-%d %H:%M:%S")}<br>'
            if obj.failure_type:
                info += f'<strong>Failure Type:</strong> {obj.get_failure_type_display()}<br>'
            return format_html(info)
        return 'No retries'

    retry_info.short_description = 'Retry Information'

    def webhook_info(self, obj):
        """Webhook reception info"""
        if obj.raw_response:
            return format_html(
                '<span style="color: green;">✓ Webhook Received</span><br>'
                '<small>at {}</small>',
                obj.created_at.strftime('%Y-%m-%d %H:%M:%S')
            )
        return format_html('<span style="color: orange;">⚠ No Webhook</span>')

    webhook_info.short_description = 'Webhook Status'

    def raw_response_display(self, obj):
        """Display raw response in readable format"""
        if obj.raw_response:
            import json
            try:
                formatted = json.dumps(obj.raw_response, indent=2)
                return format_html('<pre style="background: #f5f5f5; padding: 10px;">{}</pre>', formatted)
            except Exception:
                return str(obj.raw_response)
        return 'No response data'

    raw_response_display.short_description = 'Raw Response'

    def mark_as_completed(self, request, queryset):
        """Bulk action to mark payments as completed"""
        updated = queryset.filter(status__in=['PENDING', 'PROCESSING']).update(status='COMPLETED')
        self.message_user(request, f"{updated} payment(s) marked as completed")

    mark_as_completed.short_description = "Mark selected as completed"

    def mark_as_failed(self, request, queryset):
        """Bulk action to mark payments as failed"""
        updated = queryset.filter(status__in=['PENDING', 'PROCESSING']).update(
            status='FAILED',
            failure_type='PERMANENT'
        )
        self.message_user(request, f"{updated} payment(s) marked as failed")

    mark_as_failed.short_description = "Mark selected as failed"

    def retry_failed_payments(self, request, queryset):
        """Bulk action to reset failed payments for retry"""
        updated = queryset.filter(
            status='FAILED',
            failure_type__in=['TEMPORARY', 'USER_CANCELLED']
        ).update(
            status='PENDING',
            retry_count=0
        )
        self.message_user(request, f"{updated} payment(s) reset for retry")

    retry_failed_payments.short_description = "Reset selected for retry"

    def has_add_permission(self, request):
        """Prevent manual payment creation"""
        return False

    def has_delete_permission(self, request, obj=None):
        """Prevent deletion of completed payments"""
        if obj and obj.status == 'COMPLETED':
            return False
        return super().has_delete_permission(request, obj)