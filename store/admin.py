from django.contrib import admin
from django.db.models import Count

from .forms import ProductForm
from .models import Category, Product
from .models import NewsletterSubscription
from mptt.admin import MPTTModelAdmin, DraggableMPTTAdmin

# Unregister first to avoid conflicts during development reloads
if admin.site.is_registered(Category):
    admin.site.unregister(Category)


@admin.register(Category)
class CategoryAdmin(DraggableMPTTAdmin):
    mptt_indent_field = "name"
    list_display = ('tree_actions', 'indented_title', 'is_active', 'product_count')
    list_display_links = ('indented_title',)
    list_filter = ('is_active',)
    search_fields = ('name',)
    prepopulated_fields = {'slug': ('name',)}


    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(_product_count=Count('products'))

    def product_count(self, instance):
        return instance._product_count
    product_count.admin_order_field = '_product_count'


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    form = ProductForm
    list_display = ['name', 'category', 'price', 'discount_price', 'stock', 'available', 'on_sale']
    list_filter = ['available', 'category__parent']
    list_editable = ['price', 'available']
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ('rating', 'review_count')

    def on_sale(self, obj):
        return bool(obj.discount_price)
    on_sale.boolean = True


@admin.register(NewsletterSubscription)
class NewsletterSubscriptionAdmin(admin.ModelAdmin):
    list_display = ('email', 'confirmed', 'created_at')
    search_fields = ('email',)
    list_filter = ('confirmed',)
    readonly_fields = ('confirmation_token', 'confirmation_sent', 'confirmed_at')