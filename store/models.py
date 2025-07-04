import uuid
from django.urls import reverse
from django.conf import settings
from django.db import models
from django.utils.text import slugify
import secrets
from .constants import CATEGORIES
from mptt.models import MPTTModel, TreeForeignKey


class Category(MPTTModel):  # Change from models.Model to MPTTModel
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    image = models.ImageField(
        upload_to='categories/',
        blank=True,
        null=True,
        default='categories/default.png'
    )
    is_active = models.BooleanField(default=True)
    meta_title = models.CharField(max_length=100, blank=True)
    meta_description = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Change to TreeForeignKey
    parent = TreeForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children'
    )

    # Add MPTTMeta class
    class MPTTMeta:
        order_insertion_by = ['name']
        level_attr = 'mptt_level'

    @classmethod
    def get_default_categories(cls):
        """Class method to access the categories constant"""
        return CATEGORIES

    def __str__(self):
        # Use mptt_level instead of level
        if self.parent:
            return f'{"-" * self.mptt_level} {self.name}' if self.parent else self.name
        return self.name

    class Meta:
        verbose_name_plural = "Categories"
        ordering = ['name']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('store:product_list_by_category', args=[self.slug])

    @property
    def product_count(self):
        if hasattr(self, '_product_count_cache'):
            return self._product_count_cache
        return self.products.count()

    @product_count.setter
    def product_count(self, value):
        self._product_count_cache = value


class Product(models.Model):
    category = models.ForeignKey(
        Category,
        related_name='products',
        on_delete=models.CASCADE
    )
    id = models.AutoField(primary_key=True)
    slug = models.SlugField(max_length=200, unique=True)
    name = models.CharField(max_length=200)
    description = models.TextField()
    short_description = models.CharField(max_length=300, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    discount_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, db_index=True )
    image = models.ImageField(upload_to='products/main/')
    stock = models.PositiveIntegerField()
    available = models.BooleanField(default=True)
    featured = models.BooleanField(default=False)
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.0)
    review_count = models.PositiveIntegerField(default=0)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    is_dropship = models.BooleanField(default=False)
    supplier = models.CharField(max_length=100, blank=True)
    supplier_url = models.URLField(blank=True)
    shipping_time = models.CharField(max_length=50, default="10-20 days")
    commission_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=15.00  # Default 15% commission
    )

    class Meta:
        indexes = [
            models.Index(fields=['id', 'slug']),
        ]
        ordering = ['-created']

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            unique_id = str(uuid.uuid4())[:4]
            self.slug = f"{base_slug}-{unique_id}"

            # Ensure uniqueness
            while Product.objects.filter(slug=self.slug).exists():
                unique_id = str(uuid.uuid4())[:4]
                self.slug = f"{base_slug}-{unique_id}"
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('store:product_detail', args=[self.slug])

    def get_display_price(self):
        return self.discount_price if self.discount_price else self.price

    def update_rating(self):
        reviews = self.reviews.all()
        if reviews.exists():
            self.rating = sum(review.rating for review in reviews) / reviews.count()
            self.review_count = reviews.count()
            self.save()

    def get_discount_percentage(self):
        """Calculate discount percentage if applicable"""
        if self.discount_price and self.price and self.price > 0:
            return round((self.price - self.discount_price) / self.price * 100)
        return 0

    def __str__(self):
        return self.name



    @property
    def on_sale(self):
        return bool(self.discount_price and self.discount_price < self.price)


class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='additional_images')
    image = models.ImageField(upload_to='products/')
    color = models.CharField(max_length=50, blank=True, null=True)
    alt_text = models.CharField(max_length=100, blank=True)
    is_featured = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)


    class Meta:
        ordering = ['-is_featured', 'created_at']
        indexes = [
            models.Index(fields=['color']),
        ]


    def __str__(self):
        return f"Image for {self.product.name}"


class ProductVariant(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variants')
    size = models.CharField(max_length=20, blank=True)
    color = models.CharField(max_length=50, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.product.name} - {self.color} {self.size}"


class Review(models.Model):
    product = models.ForeignKey(Product, related_name='reviews', on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    rating = models.IntegerField(choices=[(i, i) for i in range(1, 6)])
    title = models.CharField(max_length=100)
    comment = models.TextField()
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    approved = models.BooleanField(default=False)

    class Meta:
        ordering = ('-created',)
        unique_together = ('product', 'user')  # One review per user per product

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.product.update_rating()

    def __str__(self):
        return f'Review by {self.user.username} for {self.product.name} - {self.rating} stars'

def get_discount_percentage(self):
    if self.discount_price and self.price:
        return round((self.price - self.discount_price) / self.price * 100)
    return 0



class NewsletterSubscription(models.Model):
    email = models.EmailField(unique=True)
    confirmed = models.BooleanField(default=False)
    confirmation_token = models.CharField(max_length=64)
    unsubscribe_token = models.CharField(max_length=64)
    confirmation_sent = models.DateTimeField()
    confirmed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    unsubscribed = models.BooleanField(default=False)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    source_url = models.URLField(null=True, blank=True)

    def generate_tokens(self):
        self.confirmation_token = secrets.token_urlsafe(32)
        self.unsubscribe_token = secrets.token_urlsafe(32)

    def __str__(self):
        return f"{self.email} ({'confirmed' if self.confirmed else 'pending'})"

    class Meta:
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['confirmed']),
            models.Index(fields=['unsubscribed']),
        ]