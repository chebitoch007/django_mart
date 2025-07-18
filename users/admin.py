# users/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, Profile, Address
from .forms import UserRegisterForm


class CustomUserAdmin(UserAdmin):
    model = CustomUser
    add_form = UserRegisterForm
    list_display = ('email', 'first_name', 'last_name', 'is_staff', 'last_login', 'date_joined')
    search_fields = ('email', 'first_name', 'last_name', 'phone_number')
    ordering = ('-date_joined',)

    # Remove username from fieldsets
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal Info', {'fields': ('first_name', 'last_name', 'phone_number')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Consent & Security', {'fields': (
            'terms_accepted', 'privacy_accepted', 'consent_version',
            'two_factor_enabled', 'failed_login_attempts', 'account_locked_until'
        )}),
        ('Important Dates', {'fields': ('last_login', 'date_joined')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'email',
                'first_name',
                'last_name',
                'password1',
                'password2',
                'terms_accepted',
                'privacy_accepted'
            ),
        }),
    )

    # Make email read-only after creation
    def get_readonly_fields(self, request, obj=None):
        if obj:  # Editing an existing object
            return ['email', 'consent_version', 'terms_accepted_date', 'privacy_accepted_date']
        return []


admin.site.register(CustomUser, CustomUserAdmin)


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'email_notifications', 'sms_notifications', 'marketing_optin', 'last_updated')
    raw_id_fields = ('user',)
    search_fields = ('user__email', 'user__first_name', 'user__last_name')
    list_filter = ('email_notifications', 'sms_notifications', 'marketing_optin', 'dark_mode')
    readonly_fields = ('last_updated',)

    fieldsets = (
        (None, {'fields': ('user',)}),
        ('Preferences', {'fields': (
            'email_notifications',
            'sms_notifications',
            'marketing_optin',
            'preferred_language',
            'dark_mode'
        )}),
        ('Profile Information', {'fields': ('profile_image', 'bio')}),
        ('Security', {'fields': ('two_factor_enabled',)}),
    )


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ('user', 'nickname', 'city', 'state', 'is_default')
    search_fields = ('user__email', 'street_address', 'city', 'state')
    list_filter = ('is_default', 'country')
    raw_id_fields = ('user',)

    fieldsets = (
        (None, {'fields': ('user', 'nickname', 'is_default')}),
        ('Address Information', {'fields': (
            'full_name',
            'street_address',
            'city',
            'state',
            'postal_code',
            'country',
            'phone'
        )}),
    )