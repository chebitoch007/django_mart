from django.contrib import admin
from .forms import ProductForm
from .models import Category, Product
from .models import NewsletterSubscription

# Unregister first to avoid conflicts during development reloads
if admin.site.is_registered(Category):
    admin.site.unregister(Category)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    raw_id_fields = ('parent',)
    autocomplete_fields = ['parent']
    list_display = ('name', 'parent', 'is_active', 'product_count')
    list_filter = ('parent', 'is_active')
    search_fields = ('name',)
    prepopulated_fields = {'slug': ('name',)}

    def product_count(self, obj):
        return obj.products.count()

    product_count.short_description = 'Products'


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