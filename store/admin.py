from django.contrib import admin
from .models import Category, Product, Review

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'category', 'price', 'available']
    list_filter = ['available', 'category']
    list_editable = ['price', 'available']
    prepopulated_fields = {'slug': ('name',)}  # For new products in admin

