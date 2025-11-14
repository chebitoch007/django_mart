from django.contrib import admin
from .models import (
    CompanyInfo, TeamMember, Career, JobApplication,
    Testimonial, Partner
)


@admin.register(CompanyInfo)
class CompanyInfoAdmin(admin.ModelAdmin):
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'tagline', 'description', 'founded_year', 'logo')
        }),
        ('Mission & Vision', {
            'fields': ('mission', 'vision')
        }),
        ('Contact Information', {
            'fields': ('email', 'phone', 'address')
        }),
        ('Social Media', {
            'fields': ('facebook_url', 'twitter_url', 'instagram_url', 'linkedin_url', 'youtube_url')
        }),
    )

    def has_add_permission(self, request):
        # Only allow one instance
        return not CompanyInfo.objects.exists()

    def has_delete_permission(self, request, obj=None):
        # Don't allow deletion
        return False


@admin.register(TeamMember)
class TeamMemberAdmin(admin.ModelAdmin):
    list_display = ['name', 'position', 'position_category', 'order', 'is_active']
    list_filter = ['position_category', 'is_active']
    search_fields = ['name', 'position', 'bio']
    list_editable = ['order', 'is_active']
    prepopulated_fields = {'slug': ('name',)}

    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'slug', 'position', 'position_category', 'photo')
        }),
        ('Details', {
            'fields': ('bio', 'email', 'phone', 'joined_date')
        }),
        ('Social Media', {
            'fields': ('linkedin_url', 'twitter_url')
        }),
        ('Display Settings', {
            'fields': ('order', 'is_active')
        }),
    )


@admin.register(Career)
class CareerAdmin(admin.ModelAdmin):
    list_display = ['title', 'department', 'location', 'employment_type', 'experience_level', 'is_active', 'created_at']
    list_filter = ['employment_type', 'experience_level', 'is_active', 'department']
    search_fields = ['title', 'department', 'description']
    list_editable = ['is_active']
    prepopulated_fields = {'slug': ('title',)}

    fieldsets = (
        ('Job Information', {
            'fields': ('title', 'slug', 'department', 'location', 'employment_type', 'experience_level')
        }),
        ('Description', {
            'fields': ('description', 'responsibilities', 'requirements', 'benefits')
        }),
        ('Additional Details', {
            'fields': ('salary_range', 'application_deadline')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
    )


@admin.register(JobApplication)
class JobApplicationAdmin(admin.ModelAdmin):
    list_display = ['get_full_name', 'career', 'email', 'status', 'submitted_at']
    list_filter = ['status', 'career__department', 'submitted_at']
    search_fields = ['first_name', 'last_name', 'email', 'career__title']
    list_editable = ['status']
    readonly_fields = ['submitted_at', 'updated_at']

    fieldsets = (
        ('Job Information', {
            'fields': ('career', 'status')
        }),
        ('Applicant Information', {
            'fields': ('first_name', 'last_name', 'email', 'phone')
        }),
        ('Application Materials', {
            'fields': ('resume', 'cover_letter', 'linkedin_url', 'portfolio_url')
        }),
        ('Internal Notes', {
            'fields': ('notes',)
        }),
        ('Timestamps', {
            'fields': ('submitted_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"

    get_full_name.short_description = 'Name'


@admin.register(Testimonial)
class TestimonialAdmin(admin.ModelAdmin):
    list_display = ['name', 'company', 'rating', 'is_featured', 'is_approved', 'order', 'created_at']
    list_filter = ['rating', 'is_featured', 'is_approved']
    search_fields = ['name', 'company', 'content']
    list_editable = ['is_featured', 'is_approved', 'order']

    fieldsets = (
        ('Person Information', {
            'fields': ('name', 'position', 'company', 'photo')
        }),
        ('Testimonial', {
            'fields': ('content', 'rating')
        }),
        ('Display Settings', {
            'fields': ('is_featured', 'is_approved', 'order')
        }),
    )


@admin.register(Partner)
class PartnerAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active', 'order']
    list_filter = ['is_active']
    search_fields = ['name', 'description']
    list_editable = ['is_active', 'order']

    fieldsets = (
        ('Partner Information', {
            'fields': ('name', 'logo', 'website_url', 'description')
        }),
        ('Display Settings', {
            'fields': ('is_active', 'order')
        }),
    )