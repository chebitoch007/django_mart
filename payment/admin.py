from django.contrib import admin
from .models import Payment, PaymentVerificationCode



class PaymentVerificationCodeInline(admin.TabularInline):
    model = PaymentVerificationCode
    extra = 0
    readonly_fields = ('created_at', 'expires_at', 'is_valid')
    fields = ('code', 'is_used', 'created_at', 'expires_at', 'is_valid')
    can_delete = False

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        'order_id',
        'payment_method',
        'status',
        'formatted_amount',
        'payment_deadline'
    )
    list_filter = ('status', 'method', 'created_at')
    search_fields = (
        'order__id',
        'transaction_id',
        'verification_code'
    )
    readonly_fields = (
        'created_at',
        'updated_at',
        'formatted_amount',
        'verification_code',
        'payment_method'  # Add this
    )
    fieldsets = (
        (None, {'fields': ('order', 'method', 'status')}),
        ('Financials', {'fields': ('amount', 'currency', 'formatted_amount')}),
        ('Verification', {'fields': ('verification_code', 'transaction_id')}),
        ('Timing', {'fields': ('payment_deadline', 'created_at', 'updated_at')}),
    )
    inlines = [PaymentVerificationCodeInline]
    actions = ['mark_as_paid', 'generate_verification_code']

    # Add this method to show human-readable payment method
    def payment_method(self, obj):
        return obj.get_method_display()
    payment_method.short_description = 'Payment Method'

    # Add this method to show order ID directly
    def order_id(self, obj):
        return obj.order.id
    order_id.short_description = 'Order ID'

    def formatted_amount(self, obj):
        return obj.formatted_amount
    formatted_amount.short_description = 'Amount'

    def mark_as_paid(self, request, queryset):
        updated = queryset.update(status='COMPLETED')
        self.message_user(request, f"{updated} payments marked as completed")

    def generate_verification_code(self, request, queryset):
        for payment in queryset:
            payment.generate_verification_code()
        self.message_user(request, f"Verification codes generated for {queryset.count()} payments")