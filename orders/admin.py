from django.contrib import admin
from payment.models import Payment
from .models import Order, OrderItem



class StatusFilter(admin.SimpleListFilter):
    title = 'Payment Status'
    parameter_name = 'status'

    def lookups(self, request, model_admin):
        return [
            ('PAID', 'Paid'),
            ('PENDING', 'Unpaid'),
            ('CANCELLED', 'Cancelled'),
        ]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(status=self.value())
        return None


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    raw_id_fields = ['product']
    extra = 0
    readonly_fields = ['price', 'quantity']
    verbose_name = "Order Item"
    verbose_name_plural = "Order Items"

class PaymentInline(admin.TabularInline):
    model = Payment
    readonly_fields = ['get_method_display']  # Use the display method
    fields = ['get_method_display', 'amount', 'status']

    def get_method_display(self, obj):
        return obj.get_method_display()

    get_method_display.short_description = 'Payment Method'

    def amount_currency(self, obj):
        return f"{obj.currency} {obj.amount:.2f}"
    amount_currency.short_description = 'Amount'

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'truncated_email', 'city', 'total_cost_display', 'status', 'created']
    list_filter = [StatusFilter, 'created', 'city', 'payment_method']
    search_fields = ['first_name', 'last_name', 'email', 'user__username', 'id']
    inlines = [OrderItemInline, PaymentInline]
    readonly_fields = ['created', 'updated', 'status']
    fieldsets = (
        (None, {'fields': ('user', 'status')}),
        ('Customer Information', {'fields': ('first_name', 'last_name', 'email')}),
        ('Shipping Details', {'fields': ('address', 'postal_code', 'city')}),
        ('Payment Info', {'fields': ('payment_method', 'currency')}),
        ('Dates', {'fields': ('created', 'updated')}),
    )

    def truncated_email(self, obj):
        return obj.email[:20] + '...' if len(obj.email) > 20 else obj.email
    truncated_email.short_description = 'Email'

    def total_cost_display(self, obj):
        return f"{obj.currency} {obj.total_cost:.2f}"
    total_cost_display.short_description = 'Total Amount'

    def has_change_permission(self, request, obj=None):
        # Prevent editing of completed orders
        if obj and obj.status in ['PAID', 'CANCELLED']:
            return False
        return super().has_change_permission(request, obj)