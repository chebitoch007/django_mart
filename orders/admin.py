import uuid

from django.contrib import admin
from payment.models import Payment
from .models import Order, OrderItem


class StatusFilter(admin.SimpleListFilter):
    title = 'Order Status'
    parameter_name = 'status'

    def lookups(self, request, model_admin):
        return [
            ('PAID', 'Paid'),
            ('PENDING', 'Pending'),
            ('CANCELLED', 'Cancelled'),
        ]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(status=self.value())
        return queryset

'''
class OrderItemInline(admin.TabularInline):
    model = OrderItem
    raw_id_fields = ['product']
    extra = 0
    readonly_fields = ['price', 'quantity', 'total_price_display']
    verbose_name = "Order Item"
    verbose_name_plural = "Order Items"

    def total_price_display(self, obj):
        return f"{obj.order.currency} {obj.total_price:.2f}"
    total_price_display.short_description = 'Total Price'
'''

class PaymentInline(admin.TabularInline):
    model = Payment
    readonly_fields = ['get_method_display', 'amount_currency']
    fields = ['get_method_display', 'amount_currency', 'status']

    def get_method_display(self, obj):
        return obj.get_method_display()

    get_method_display.short_description = 'Payment Method'

    def amount_currency(self, obj):
        return f"{obj.currency} {obj.amount:.2f}"
    amount_currency.short_description = 'Amount'

'''
@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'user',
        'truncated_email',
        'city',
        'total_cost_display',
        'status',
        'payment_method',
        'created'
    ]
    list_filter = [StatusFilter, 'created', 'city', 'payment_method']
    search_fields = ['first_name', 'last_name', 'email', 'user__username', 'id']
    inlines = [OrderItemInline, PaymentInline]
    readonly_fields = ['created', 'updated', 'total_cost_display']
    fieldsets = (
        (None, {'fields': ('user', 'status', 'payment_method')}),
        ('Customer Information', {'fields': ('first_name', 'last_name', 'email')}),
        ('Shipping Details', {'fields': ('address', 'postal_code', 'city')}),
        ('Payment Info', {'fields': ('currency', 'total_cost_display')}),
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

'''




class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('product', 'price', 'quantity',)
    fields = ('product', 'price', 'quantity', 'dropship_processed', 'tracking_number', 'estimated_delivery')

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'status', 'total_cost', 'created')
    list_filter = ('status', 'created')
    search_fields = ('id', 'user__email', 'first_name', 'last_name')
    inlines = [OrderItemInline]
    actions = ['process_dropship_orders']

    def process_dropship_orders(self, request, queryset):
        for order in queryset:
            for item in order.items.filter(product__is_dropship=True, dropship_processed=False):
                # This would be manual processing in real scenario
                item.tracking_number = f"MANUAL-{uuid.uuid4().hex[:8]}"
                item.estimated_delivery = "10-20 days"
                item.dropship_processed = True
                item.save()
        self.message_user(request, f"Processed {queryset.count()} orders")

    process_dropship_orders.short_description = "Process dropship orders"