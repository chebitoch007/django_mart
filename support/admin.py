from django.contrib import admin
from .models import (
    TicketCategory, SupportTicket, TicketMessage,
    FAQ, ContactMessage
)


@admin.register(TicketCategory)
class TicketCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'order', 'is_active']
    list_editable = ['order', 'is_active']
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ['name', 'description']


class TicketMessageInline(admin.TabularInline):
    model = TicketMessage
    extra = 0
    readonly_fields = ['created_at']
    fields = ['user', 'message', 'is_staff_reply', 'attachment', 'created_at']


@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = ['ticket_number', 'subject', 'user', 'category', 'status', 'priority', 'created_at']
    list_filter = ['status', 'priority', 'category', 'created_at']
    search_fields = ['ticket_number', 'subject', 'user__email', 'description']
    readonly_fields = ['ticket_number', 'created_at', 'updated_at', 'resolved_at']
    list_editable = ['status', 'priority']
    inlines = [TicketMessageInline]

    fieldsets = (
        ('Ticket Information', {
            'fields': ('ticket_number', 'user', 'category', 'subject', 'description')
        }),
        ('Status & Priority', {
            'fields': ('status', 'priority', 'assigned_to')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'resolved_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    list_display = ['question', 'category', 'order', 'helpful_count', 'views', 'is_published']
    list_filter = ['category', 'is_published']
    search_fields = ['question', 'answer']
    list_editable = ['order', 'is_published']
    readonly_fields = ['views', 'helpful_count', 'not_helpful_count', 'created_at', 'updated_at']


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ['subject', 'name', 'email', 'is_read', 'replied', 'created_at']
    list_filter = ['is_read', 'replied', 'created_at']
    search_fields = ['name', 'email', 'subject', 'message']
    list_editable = ['is_read', 'replied']
    readonly_fields = ['created_at']

    fieldsets = (
        ('Contact Information', {
            'fields': ('name', 'email', 'phone', 'user')
        }),
        ('Message', {
            'fields': ('subject', 'message')
        }),
        ('Status', {
            'fields': ('is_read', 'replied', 'created_at')
        }),
    )