# payment/admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Q
from .models import (
    Payment,
    PaymentMethod,
    PaymentVerificationCode,
    CurrencyExchangeRate,
    PaymentGatewaySettings
)
from django.utils import timezone
from django.contrib import messages


class PaymentVerificationCodeInline(admin.TabularInline):
    model = PaymentVerificationCode
    extra = 0
    max_num = 3
    readonly_fields = ('code', 'is_used', 'created_at', 'expires_at', 'is_valid')
    fields = ('code', 'is_used', 'is_valid', 'created_at', 'expires_at')
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        'order_id',
        'user_info',
        'payment_method_display',
        'status_badge',
        'formatted_amount',
        'refund_status',
        'payment_deadline',
        'time_remaining'
    )
    list_filter = (
        'status',
        'method',
        'currency',
        'created_at',
        'refund_requested',  # New filter
        ('payment_method', admin.RelatedOnlyFieldListFilter)
    )
    search_fields = (
        'order__id',
        'transaction_id',
        'verification_code',
        'user__username',
        'user__email'
    )
    readonly_fields = (
        'created_at',
        'updated_at',
        'formatted_amount',
        'time_remaining',
        'gateway_response_preview',
        'verification_code',
        'transaction_id'
    )
    fieldsets = (
        ('Refund Management', {
            'fields': (
                'refund_requested',
                'refund_amount',
                'refund_reason',
                'refund_requested_at',
                'refund_processed_at'
            ),
            'classes': ('collapse',)
        }),
        ('Order Information', {
            'fields': (
                'order',
                'user_info',
                'transaction_id'
            )
        }),
        ('Payment Details', {
            'fields': (
                'method',
                'status',
                'payment_method',
                'amount',
                'currency',
                'formatted_amount'
            )
        }),
        ('Security & Verification', {
            'fields': (
                'verification_code',
                'payment_deadline',
                'time_remaining'
            )
        }),
        ('Gateway Response', {
            'fields': ('gateway_response_preview',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
        ('Error Handling', {
            'fields': ('error_code', 'error_message'),
            'classes': ('collapse',)
        }),
    )
    inlines = [PaymentVerificationCodeInline]

    def refund_status(self, obj):
        if obj.status == 'REFUNDED':
            return format_html(
                '<span style="color:green">✓ Refunded</span>'
            )
        elif obj.refund_requested:
            return format_html(
                '<span style="color:orange">Refund Pending</span>'
            )
        return "-"
    refund_status.short_description = 'Refund Status'

    actions = [
        'mark_as_paid',
        'mark_as_failed',
        'generate_verification_code',
        'resend_payment_notification',
        'request_refund',
        'process_refund',
    ]
    list_per_page = 20
    date_hierarchy = 'created_at'

    def request_refund(self, request, queryset):
        # In real implementation, show a form for amount/reason
        for payment in queryset:
            if payment.status != 'COMPLETED':
                self.message_user(
                    request,
                    f"Payment #{payment.id} not completed - skipped",
                    messages.WARNING
                )
                continue

            payment.request_refund(
                amount=payment.amount,
                reason="Admin-initiated refund"
            )
        self.message_user(request, f"{queryset.count()} refund requests initiated")

    def process_refund(self, request, queryset):
        for payment in queryset:
            if payment.status != 'REFUND_PENDING':
                self.message_user(
                    request,
                    f"Payment #{payment.id} not pending refund - skipped",
                    messages.WARNING
                )
                continue

            payment.process_refund()
        self.message_user(request, f"{queryset.count()} refunds processed")

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'order',
            'order__user',
            'payment_method'
        )

    def user_info(self, obj):
        if not obj.order or not obj.order.user:
            return "-"
        user = obj.order.user
        return format_html(
            '<a href="{}">{} ({})</a>',
            f"/admin/auth/user/{user.id}/change/",
            user.get_full_name() or user.username,
            user.email
        )

    user_info.short_description = 'User'

    def payment_method_display(self, obj):
        if not obj.payment_method:
            return "-"

        if obj.payment_method.method_type in ['VISA', 'MASTERCARD']:
            return f"{obj.payment_method.get_method_type_display()} •••• {obj.payment_method.last_4_digits}"
        return str(obj.payment_method)

    payment_method_display.short_description = 'Payment Method'

    def status_badge(self, obj):
        color_map = {
            'PENDING': 'blue',
            'COMPLETED': 'green',
            'FAILED': 'red',
            'REFUNDED': 'orange',
            'PROCESSING': 'purple',
        }
        color = color_map.get(obj.status, 'gray')
        return format_html(
            '<span style="background:{}; color:white; padding:2px 8px; border-radius:10px">{}</span>',
            color,
            obj.get_status_display()
        )

    status_badge.short_description = 'Status'
    status_badge.admin_order_field = 'status'

    def gateway_response_preview(self, obj):
        if not obj.gateway_response:
            return "-"
        return format_html(
            '<pre style="max-height: 200px; overflow:auto">{}</pre>',
            str(obj.gateway_response)
        )

    gateway_response_preview.short_description = 'Gateway Response'

    def mark_as_paid(self, request, queryset):
        for payment in queryset:
            payment.mark_as_paid()
        self.message_user(request, f"{queryset.count()} payments marked as paid")

    mark_as_paid.short_description = "Mark selected as paid"

    def mark_as_failed(self, request, queryset):
        for payment in queryset:
            payment.mark_as_failed(error_message="Manually marked as failed")
        self.message_user(request, f"{queryset.count()} payments marked as failed")

    mark_as_failed.short_description = "Mark selected as failed"

    def generate_verification_code(self, request, queryset):
        for payment in queryset:
            payment.generate_verification_code()
        self.message_user(request, f"Verification codes generated for {queryset.count()} payments")

    generate_verification_code.short_description = "Generate verification codes"

    def resend_payment_notification(self, request, queryset):
        # This would call your notification service in a real implementation
        count = queryset.count()
        self.message_user(request, f"Payment notifications resent for {count} orders")

    resend_payment_notification.short_description = "Resend payment notification"




@admin.register(PaymentMethod)
class PaymentMethodAdmin(admin.ModelAdmin):
    list_display = (
        'user_info',
        'method_type_display',
        'sensitive_info_preview',
        'is_default',
        'is_active',
        'created_at'
    )
    list_filter = ('method_type', 'is_default', 'is_active', 'created_at')
    search_fields = (
        'user__username',
        'user__email',
        'last_4_digits',
        'phone_number',
        'paypal_email'
    )
    readonly_fields = (
        'method_type',
        'last_4_digits',
        'expiration_month',
        'expiration_year',
        'card_type',
        'created_at',
        'updated_at',
        'sensitive_info_preview'
    )
    fieldsets = (
        ('User Information', {
            'fields': ('user', 'is_active', 'is_default')
        }),
        ('Method Details', {
            'fields': (
                'method_type',
                'sensitive_info_preview',
                'last_4_digits',
                'expiration_month',
                'expiration_year',
                'card_type'
            )
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    actions = ['deactivate_methods', 'set_as_default']
    list_per_page = 20
    date_hierarchy = 'created_at'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')

    def user_info(self, obj):
        return format_html(
            '<a href="{}">{} ({})</a>',
            f"/admin/auth/user/{obj.user.id}/change/",
            obj.user.get_full_name() or obj.user.username,
            obj.user.email
        )

    user_info.short_description = 'User'

    def method_type_display(self, obj):
        return obj.get_method_type_display()

    method_type_display.short_description = 'Type'
    method_type_display.admin_order_field = 'method_type'

    def sensitive_info_preview(self, obj):
        if obj.method_type == 'PAYPAL':
            return f"PayPal: {obj.paypal_email}"
        elif obj.method_type in ['MPESA', 'AIRTEL']:
            return f"Phone: {obj.phone_number}"
        elif obj.method_type in ['VISA', 'MASTERCARD']:
            return f"Card: •••• {obj.last_4_digits} ({obj.expiration_month}/{obj.expiration_year})"
        return "-"

    sensitive_info_preview.short_description = 'Payment Details'

    def deactivate_methods(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"{updated} payment methods deactivated")

    deactivate_methods.short_description = "Deactivate selected methods"

    def set_as_default(self, request, queryset):
        for method in queryset:
            method.is_default = True
            method.save()
        self.message_user(request, f"{queryset.count()} methods set as default")

    set_as_default.short_description = "Set as default payment method"


@admin.register(CurrencyExchangeRate)
class CurrencyExchangeRateAdmin(admin.ModelAdmin):
    list_display = (
        'pair_display',
        'rate',
        'last_updated'
    )
    list_filter = ('base_currency', 'target_currency')
    search_fields = ('base_currency', 'target_currency')
    readonly_fields = ('last_updated',)
    list_editable = ('rate',)
    list_per_page = 20
    date_hierarchy = 'last_updated'

    def pair_display(self, obj):
        return f"{obj.base_currency} → {obj.target_currency}"

    pair_display.short_description = 'Currency Pair'


@admin.register(PaymentGatewaySettings)
class PaymentGatewaySettingsAdmin(admin.ModelAdmin):
    list_display = (
        'provider',
        'is_active',
        'priority',
        'supported_countries_count',
        'supported_currencies_count'
    )
    list_filter = ('is_active',)
    search_fields = ('provider',)
    list_editable = ('is_active', 'priority')


    def supported_countries_count(self, obj):
        return len(obj.supported_countries)

    supported_countries_count.short_description = 'Countries'

    def supported_currencies_count(self, obj):
        return len(obj.supported_currencies)

    supported_currencies_count.short_description = 'Currencies'


@admin.register(PaymentVerificationCode)
class PaymentVerificationCodeAdmin(admin.ModelAdmin):
    list_display = (
        'code',
        'payment_link',
        'is_used',
        'is_valid',
        'expires_at'
    )
    list_filter = ('is_used', 'expires_at')
    search_fields = ('code', 'payment__order__id')
    readonly_fields = (
        'code',
        'payment',
        'is_used',
        'is_valid',
        'created_at',
        'expires_at'
    )
    date_hierarchy = 'expires_at'

    def payment_link(self, obj):
        return format_html(
            '<a href="{}">Payment #{}</a>',
            f"/admin/payment/payment/{obj.payment.id}/change/",
            obj.payment.id
        )

    payment_link.short_description = 'Payment'

    def has_add_permission(self, request):
        return False