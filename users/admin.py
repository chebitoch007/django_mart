# users/admin.py

import json
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from .models import CustomUser, Profile, Address, ActivityLog, PasswordHistory
from .forms import UserRegisterForm


class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    verbose_name_plural = 'Profile'
    fk_name = 'user'
    fields = ('profile_image', 'bio', 'email_notifications', 'sms_notifications',
              'marketing_optin', 'preferred_language', 'dark_mode')


class AddressInline(admin.TabularInline):
    model = Address
    extra = 0
    fields = ('nickname', 'address_type', 'street_address', 'city', 'state',
              'postal_code', 'country', 'is_default')
    readonly_fields = ('created', 'updated')


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    model = CustomUser
    add_form = UserRegisterForm
    list_display = ('email', 'full_name', 'phone_number', 'is_staff', 'is_active',
                    'email_verified', 'last_login', 'date_joined')
    list_filter = ('is_staff', 'is_active', 'email_verified', 'phone_verified',
                   'two_factor_enabled', 'date_joined')
    search_fields = ('email', 'first_name', 'last_name', 'phone_number')
    ordering = ('-date_joined',)
    inlines = [ProfileInline, AddressInline]

    # Fieldsets for viewing/editing existing users
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal Info', {
            'fields': ('first_name', 'last_name', 'phone_number', 'public_id')
        }),
        ('Verification Status', {
            'fields': ('email_verified', 'phone_verified')
        }),
        ('Permissions', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')
        }),
        ('Consent & Privacy', {
            'fields': ('terms_accepted', 'privacy_accepted', 'consent_version',
                       'terms_accepted_date', 'privacy_accepted_date'),
            'classes': ('collapse',)
        }),
        ('Security', {
            'fields': ('two_factor_enabled', 'two_factor_method', 'failed_login_attempts',
                       'account_locked_until', 'last_password_update'),
            'classes': ('collapse',)
        }),
        ('Login Information', {
            'fields': ('last_login', 'last_login_ip', 'last_login_device'),
            'classes': ('collapse',)
        }),
        ('Important Dates', {
            'fields': ('date_joined', 'created_at', 'updated_at')
        }),
    )

    # Fieldsets for adding new users
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'email',
                'first_name',
                'last_name',
                'phone_number',
                'password1',
                'password2',
                'is_staff',
                'is_active',
                'terms_accepted',
                'privacy_accepted'
            ),
        }),
    )

    readonly_fields = ('public_id', 'consent_version', 'terms_accepted_date',
                       'privacy_accepted_date', 'last_password_update',
                       'date_joined', 'created_at', 'updated_at', 'last_login')

    def full_name(self, obj):
        """Display full name"""
        return obj.get_full_name() or obj.email

    full_name.short_description = 'Name'

    def get_readonly_fields(self, request, obj=None):
        """Make email read-only after creation"""
        if obj:  # Editing an existing object
            return self.readonly_fields + ('email',)
        return self.readonly_fields

    def save_model(self, request, obj, form, change):
        """Override to handle consent timestamps"""
        if not change:  # New user
            if obj.terms_accepted and not obj.terms_accepted_date:
                obj.terms_accepted_date = timezone.now()
            if obj.privacy_accepted and not obj.privacy_accepted_date:
                obj.privacy_accepted_date = timezone.now()
        super().save_model(request, obj, form, change)


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = (
        'user_link', 'email_notifications', 'sms_notifications',
        'marketing_optin', 'dark_mode', 'preferred_language', 'last_updated'
    )
    list_filter = (
        'email_notifications', 'sms_notifications', 'marketing_optin',
        'dark_mode', 'preferred_language'
    )
    search_fields = ('user__email', 'user__first_name', 'user__last_name')
    readonly_fields = ('last_updated', 'user_info')
    raw_id_fields = ('user',)
    date_hierarchy = 'last_updated'
    ordering = ('-last_updated',)

    fieldsets = (
        ('User', {'fields': ('user_info', 'user')}),
        ('Profile Information', {
            'fields': ('profile_image', 'bio', 'date_of_birth')
        }),
        ('Notification Preferences', {
            'fields': ('email_notifications', 'sms_notifications', 'marketing_optin')
        }),
        ('Personalization', {
            'fields': ('preferred_language', 'dark_mode')
        }),
        ('Security', {
            'fields': ('two_factor_enabled',)
        }),
        ('Metadata', {
            'fields': ('last_updated',),
            'classes': ('collapse',)
        }),
    )

    # === Custom Display Methods ===

    def user_link(self, obj):
        """Clickable link to User admin"""
        url = reverse('admin:users_customuser_change', args=[obj.user.id])
        return format_html('<a href="{}">{}</a>', url, obj.user.email)
    user_link.short_description = 'User'

    def user_info(self, obj):
        """Display rich user summary"""
        url = reverse('admin:users_customuser_change', args=[obj.user.id])
        return format_html(
            '<a href="{}"><strong>{}</strong></a><br>'
            '<small>Email: {}</small><br>'
            '<small>Joined: {}</small>',
            url,
            obj.user.get_full_name() or obj.user.email,
            obj.user.email,
            obj.user.date_joined.strftime('%Y-%m-%d')
        )
    user_info.short_description = 'User Information'


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ('user_link', 'nickname', 'address_type', 'city', 'state',
                    'country', 'is_default', 'created')
    list_filter = ('address_type', 'is_default', 'country', 'created')
    search_fields = ('user__email', 'full_name', 'street_address', 'city',
                     'state', 'nickname')
    readonly_fields = ('created', 'updated')
    raw_id_fields = ('user',)
    date_hierarchy = 'created'

    fieldsets = (
        ('User', {'fields': ('user',)}),
        ('Address Identification', {
            'fields': ('nickname', 'address_type', 'is_default')
        }),
        ('Contact Information', {
            'fields': ('full_name', 'phone')
        }),
        ('Address Details', {
            'fields': ('street_address', 'city', 'state', 'postal_code', 'country')
        }),
        ('Timestamps', {
            'fields': ('created', 'updated'),
            'classes': ('collapse',)
        }),
    )

    def user_link(self, obj):
        """Link to user admin"""
        url = reverse('admin:users_customuser_change', args=[obj.user.id])
        return format_html('<a href="{}">{}</a>', url, obj.user.email)

    user_link.short_description = 'User'


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'user_link', 'activity_type', 'ip_address',
        'timestamp', 'user_agent_short'
    )
    list_filter = ('activity_type', 'timestamp')
    search_fields = ('user__email', 'ip_address', 'user_agent')
    readonly_fields = (
        'user', 'activity_type', 'ip_address', 'user_agent',
        'timestamp', 'additional_info_display'
    )
    date_hierarchy = 'timestamp'
    ordering = ('-timestamp',)

    fieldsets = (
        ('Activity Information', {
            'fields': ('user', 'activity_type', 'timestamp')
        }),
        ('Request Details', {
            'fields': ('ip_address', 'user_agent')
        }),
        ('Additional Information', {
            'fields': ('additional_info_display',),
            'classes': ('collapse',)
        }),
    )

    # === Custom Display Methods ===

    def user_link(self, obj):
        """Clickable link to User admin or 'Anonymous'"""
        if obj.user:
            url = reverse('admin:users_customuser_change', args=[obj.user.id])
            return format_html('<a href="{}">{}</a>', url, obj.user.email)
        return 'Anonymous'
    user_link.short_description = 'User'

    def user_agent_short(self, obj):
        """Shorten long user agent strings"""
        ua = obj.user_agent or '-'
        return ua[:50] + '...' if len(ua) > 50 else ua
    user_agent_short.short_description = 'User Agent'

    def additional_info_display(self, obj):
        """Formatted JSON in <pre> block"""
        if not obj.additional_info:
            return 'No additional information'
        try:
            formatted = json.dumps(obj.additional_info, indent=2)
            return format_html('<pre>{}</pre>', formatted)
        except Exception:
            return str(obj.additional_info)
    additional_info_display.short_description = 'Additional Information'

    # === Permissions ===
    def has_add_permission(self, request):
        return False  # no manual creation

    def has_change_permission(self, request, obj=None):
        return False  # locked logs

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser  # allow cleanup


@admin.register(PasswordHistory)
class PasswordHistoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'user_link', 'created_at', 'age_display')
    list_filter = ('created_at',)
    search_fields = ('user__email', 'user__first_name', 'user__last_name')
    readonly_fields = ('user', 'password', 'created_at')
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)

    fieldsets = (
        ('Password History', {
            'fields': ('user', 'password', 'created_at')
        }),
    )

    def user_link(self, obj):
        """Link to user admin"""
        url = reverse('admin:users_customuser_change', args=[obj.user.id])
        return format_html('<a href="{}">{}</a>', url, obj.user.email)

    user_link.short_description = 'User'

    def age_display(self, obj):
        """Show how old the password record is"""
        delta = timezone.now() - obj.created_at
        days = delta.days

        if days == 0:
            return 'Today'
        elif days == 1:
            return 'Yesterday'
        elif days < 7:
            return f'{days} days ago'
        elif days < 30:
            weeks = days // 7
            return f'{weeks} week{"s" if weeks > 1 else ""} ago'
        else:
            months = days // 30
            return f'{months} month{"s" if months > 1 else ""} ago'

    age_display.short_description = 'Age'

    def has_add_permission(self, request):
        """Prevent manual creation"""
        return False

    def has_change_permission(self, request, obj=None):
        """Prevent modification"""
        return False

    def has_delete_permission(self, request, obj=None):
        """Allow deletion for cleanup (superuser only)"""
        return request.user.is_superuser