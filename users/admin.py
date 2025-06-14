from django.contrib import admin
from .models import CustomUser, Profile

@admin.register(CustomUser)
class CustomUserAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'county', 'last_login')
    search_fields = ('username', 'email', 'phone_number')

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'email_notifications', 'sms_notifications')
    raw_id_fields = ('user',)