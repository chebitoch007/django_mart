
from django.contrib import admin
from .models import CustomUser, Profile, Address
from django.contrib.auth.admin import UserAdmin
from .forms import UserRegisterForm

class CustomUserAdmin(UserAdmin):
    model = CustomUser
    add_form = UserRegisterForm
    list_display = ('username', 'email', 'county', 'last_login', 'date_joined')
    search_fields = ('username', 'email', 'phone_number')
    ordering = ('-date_joined',)
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal Info', {'fields': ('first_name', 'last_name', 'email', 'phone_number', 'county', 'town')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important Dates', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'phone_number', 'password1', 'password2'),
        }),
    )


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'email_notifications', 'sms_notifications', 'last_updated')
    raw_id_fields = ('user',)
    search_fields = ('user__username', 'user__email')
    list_filter = ('email_notifications', 'sms_notifications', 'dark_mode')
    readonly_fields = ('last_updated',)

@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ('user', 'nickname', 'city', 'state', 'is_default')
    search_fields = ('user__username', 'street_address', 'city', 'state')
    list_filter = ('is_default', 'country')
    raw_id_fields = ('user',)

