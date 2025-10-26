# store/models.py
import logging
from django.db import transaction
import uuid
from django.db.models import Q, Value, CharField, TextField
from django.templatetags.static import static
from django.urls import reverse
from django.conf import settings
from django.db import models
from django.utils.text import slugify
import secrets
from .constants import CATEGORIES
from mptt.models import MPTTModel, TreeForeignKey
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField, SearchVector

logger = logging.getLogger(__name__)

class Category(MPTTModel):
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    image = models.ImageField(upload_to='categories/', blank=True, null=True, default='')
    is_active = models.BooleanField(default=True)
    meta_title = models.CharField(max_length=100, blank=True)
    meta_description = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    parent = TreeForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children')

    class MPTTMeta:
        order_insertion_by = ['name']
        level_attr = 'mptt_level'

    @classmethod
    def get_default_categories(cls):
        return CATEGORIES

    def __str__(self):
        if self.parent:
            return f'{"-" * self.mptt_level} {self.name}'
        return self.name

    class Meta:
        verbose_name_plural = "Categories"
        ordering = ['name']

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            unique_slug = base_slug
            counter = 1
            while Category.objects.filter(slug=unique_slug).exclude(pk=self.pk).exists():
                unique_slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = unique_slug
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


class SearchLog(models.Model):
    query = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['query']),
            models.Index(fields=['created_at']),
        ]
        ordering = ['-created_at']


class Supplier(models.Model):
    """Normalized supplier table so we can join and search safely."""
    name = models.CharField(max_length=150, unique=True)
    website = models.URLField(blank=True)
    notes = models.TextField(blank=True)

    def __str__(self):
        return self.name


class Brand(models.Model):
    """Optional product brand for filtering / search / facets."""
    name = models.CharField(max_length=150, unique=True)
    slug = models.SlugField(max_length=160, unique=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class ProductQuerySet(models.QuerySet):
    def search(self, query):
        if not query:
            return self.none()

        # Keep search responsibilities in views/helpers; this is a convenience method.
        return self.filter(
            Q(name__icontains=query) |
            Q(short_description__icontains=query) |
            Q(description__icontains=query) |
            Q(category__name__icontains=query) |
            Q(brand__name__icontains=query) |
            Q(supplier__name__icontains=query)
        )


class ProductManager(models.Manager):
    def get_queryset(self):
        return ProductQuerySet(self.model, using=self._db)

    def search(self, query):
        return self.get_queryset().search(query)


class Product(models.Model):
    category = models.ForeignKey('Category', related_name='products', on_delete=models.CASCADE)
    id = models.AutoField(primary_key=True)
    slug = models.SlugField(max_length=200, unique=True)
    name = models.CharField(max_length=200)
    description = models.TextField()
    short_description = models.CharField(max_length=300, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    discount_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, db_index=True)
    image = models.ImageField(upload_to='products/main/')
    stock = models.PositiveIntegerField()
    available = models.BooleanField(default=True)
    featured = models.BooleanField(default=False)
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.0)
    review_count = models.PositiveIntegerField(default=0, db_index=True)  # keep for cached count
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    # New normalized relations
    brand = models.ForeignKey(Brand, null=True, blank=True, related_name='products', on_delete=models.SET_NULL)
  #  supplier = models.ForeignKey(Supplier, null=True, blank=True, related_name='products', on_delete=models.SET_NULL)
    # OLD supplier name stored temporarily
    supplier_name = models.CharField(max_length=150, blank=True, null=True)

    # NEW relational supplier model
    supplier = models.ForeignKey(
        'Supplier',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='products'
    )
    supplier_url = models.URLField(blank=True)

    # Dropship extras
    is_dropship = models.BooleanField(default=False)
    shipping_time = models.CharField(max_length=50, default="10-20 days")
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2, default=15.00)
    supplier_product_id = models.CharField(max_length=100, blank=True)
    package_dimensions = models.CharField(max_length=100, blank=True)
    package_weight = models.DecimalField(max_digits=6, decimal_places=2, default=0)

    # Search support (denormalized text fields used to build search_vector)
    search_vector = SearchVectorField(null=True, blank=True)
    search_name = models.CharField(max_length=255, blank=True)
    search_description = models.TextField(blank=True)
    search_category = models.CharField(max_length=100, blank=True)
    search_brand = models.CharField(max_length=150, blank=True)
    search_supplier = models.CharField(max_length=150, blank=True)

    objects = ProductManager()

    def save(self, *args, **kwargs):
        # Generate unique slug if not set
        if not self.slug:
            base_slug = slugify(self.name)
            unique_id = str(uuid.uuid4())[:4]
            self.slug = f"{base_slug}-{unique_id}"
            while Product.objects.filter(slug=self.slug).exists():
                unique_id = str(uuid.uuid4())[:4]
                self.slug = f"{base_slug}-{unique_id}"

        # Populate denormalized search fields for later vector update
        self.search_name = self.name or ''
        self.search_description = self.description or ''
        self.search_category = self.category.name if self.category else ''
        self.search_brand = self.brand.name if self.brand else ''
        self.search_supplier = self.supplier.name if self.supplier else ''

        super().save(*args, **kwargs)

        # Update search_vector using Value(...) to avoid DB joins inside the update.
        # Use transaction.atomic to guarantee the object exists when updating.
        with transaction.atomic():
            Product.objects.filter(pk=self.pk).update(
                search_vector=(
                    # explicit output_field for each Value to keep Postgres happy
                    # weights A/B/C chosen per field importance
                    SearchVector(Value(self.search_name, output_field=CharField()), weight='A') +
                    SearchVector(Value(self.search_description, output_field=TextField()), weight='B') +
                    SearchVector(Value(self.search_category, output_field=CharField()), weight='C') +
                    SearchVector(Value(self.search_brand, output_field=CharField()), weight='B') +
                    SearchVector(Value(self.search_supplier, output_field=CharField()), weight='C')
                )
            )

    def update_search_vector(self):
        category_name = Category.objects.filter(pk=self.category_id).values_list('name', flat=True).first() or ''
        brand_name = Brand.objects.filter(pk=self.brand_id).values_list('name', flat=True).first() or ''
        supplier_name = Supplier.objects.filter(pk=self.supplier_id).values_list('name', flat=True).first() or ''
        with transaction.atomic():
            Product.objects.filter(pk=self.pk).update(
                search_vector=(
                    SearchVector(Value(self.name, output_field=CharField()), weight='A') +
                    SearchVector(Value(self.short_description, output_field=CharField()), weight='B') +
                    SearchVector(Value(self.description, output_field=TextField()), weight='B') +
                    SearchVector(Value(category_name, output_field=CharField()), weight='C') +
                    SearchVector(Value(brand_name, output_field=CharField()), weight='B') +
                    SearchVector(Value(supplier_name, output_field=CharField()), weight='C')
                )
            )

    def get_image_url(self):
        """
        Returns the URL of the product's primary image,
        falling back to a placeholder if missing.
        """
        try:
            if self.image:
                url = self.image.url
                logger.debug(f"[Product.get_image_url] Product '{self.name}' has image field='{self.image}', resolved URL='{url}'")
                return url
            else:
                logger.warning(f"[Product.get_image_url] Product '{self.name}' has no image assigned, using placeholder.")
                return '/static/store/images/placeholder.png'
        except Exception as e:
            logger.error(f"[Product.get_image_url] Error resolving image for '{self.name}': {e}", exc_info=True)
            return '/static/store/images/placeholder.png'

    def get_large_image_url(self):
        """Returns the URL for a large version of the image, for zoom."""

        # For simplicity, this returns the main image.
        # You could replace this with logic for a larger, watermarked,
        # or different-sized image if you have one.

        if self.image and self.image.name:
            return self.image.url
        return static('store/images/placeholder.png')


    def get_absolute_url(self):
        return reverse('store:product_detail', args=[self.slug])

    def get_display_price(self):
        return self.discount_price if self.discount_price else self.price

    def update_rating(self):
        reviews = self.reviews.all()
        if reviews.exists():
            self.rating = sum(review.rating for review in reviews) / reviews.count()
            self.review_count = reviews.count()
            self.save(update_fields=['rating', 'review_count', 'updated'])

    def get_discount_percentage(self):
        if self.discount_price and self.price and self.price > 0:
            return round((self.price - self.discount_price) / self.price * 100)
        return 0

    @property
    def on_sale(self):
        return bool(self.discount_price and self.discount_price < self.price)

    def __str__(self):
        return self.name

    class Meta:
        indexes = [
            GinIndex(fields=['search_vector']),
            models.Index(fields=['name']),
            models.Index(fields=['price']),
        ]
        ordering = ['-created']


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

class StockNotification(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='notifications')
    email = models.EmailField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('product', 'email')
        indexes = [
            models.Index(fields=['product', 'email']),
        ]

    def __str__(self):
        return f"Notification for {self.product.name} at {self.email}"

class Review(models.Model):
    product = models.ForeignKey(Product, related_name='reviews', on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    rating = models.IntegerField(choices=[(i, i) for i in range(1, 6)])
    title = models.CharField(max_length=100)
    comment = models.TextField()
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    approved = models.BooleanField(default=False)
    helpful_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ('-created',)
        unique_together = ('product', 'user')

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Keep product rating counters in sync
        try:
            self.product.update_rating()
        except Exception:
            pass

    def __str__(self):
        return f'Review by {self.user.username} for {self.product.name} - {self.rating} stars'


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
