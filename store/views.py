from store.aliexpress import import_aliexpress_product
from .forms import ImportProductsForm
from django.shortcuts import render, get_object_or_404, redirect
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Avg, Q, Count, F, ExpressionWrapper, DecimalField, Prefetch
from django.views.generic import TemplateView, ListView
from .models import Category, Product, Review, NewsletterSubscription, ProductImage, SearchLog
from cart.forms import CartAddProductForm
from .forms import ReviewForm
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.contrib import messages
from django.views.decorators.http import require_POST, require_GET
from django.utils import timezone
from .utils import send_email_async
import logging
from django.http import HttpRequest, JsonResponse
from django.urls import reverse
from django.db.models.functions import Coalesce, Greatest
from store.constants import CATEGORIES
from django.contrib.auth.decorators import login_required, user_passes_test
from django.forms import inlineformset_factory
from .forms import ProductForm, ProductImageFormSet
from .aliexpress import generate_affiliate_link
from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank, TrigramSimilarity
from django.core.cache import cache
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page


from django.db import connection
import json

SORT_OPTIONS = {
    'price_asc': 'price',
    'price_desc': '-price',
    'name': 'name',
    'rating': '-avg_rating',
    'popular': '-review_count',
    'newest': '-created',
    'discount': '-discount_percentage',
}

# Constants
SEARCH_WEIGHTS = [0.1, 0.2, 0.4, 1.0]  # D, C, B, A weights
SUGGESTION_THRESHOLD = 0.15  # Minimum similarity for suggestions
TRENDING_CACHE_KEY = 'trending_products'
TRENDING_CACHE_TIMEOUT = 3600  # 1 hour


@require_GET
def product_search(request):
    query = request.GET.get('q', '').strip()
    category_slug = request.GET.get('category')
    sort_by = request.GET.get('sort', '-created')
    max_price = request.GET.get('max_price')
    min_rating = request.GET.get('min_rating')
    in_stock = request.GET.get('in_stock') == 'true'

    if not query:
        return redirect('store:product_list')

    # Full-text search with PostgreSQL
    search_query = SearchQuery(query, config='english')
    vector = (
            SearchVector('name', weight='A') +
            SearchVector('short_description', weight='B') +
            SearchVector('description', weight='C') +
            SearchVector('category__name', weight='A')
    )

    products = Product.objects.annotate(
        rank=SearchRank(vector, search_query, weights=SEARCH_WEIGHTS),
        similarity=Greatest(
            TrigramSimilarity('name', query),
            TrigramSimilarity('short_description', query),
            TrigramSimilarity('description', query),
            TrigramSimilarity('category__name', query)
        )
    ).filter(
        (Q(rank__gte=0.1) | Q(similarity__gt=SUGGESTION_THRESHOLD)),
        available=True
    )

    # Apply filters
    if category_slug:
        products = products.filter(category__slug=category_slug)

    if max_price and max_price.isdigit():
        products = products.filter(price__lte=int(max_price))

    if in_stock:
        products = products.filter(stock__gt=0)

    if min_rating and min_rating.isdigit():
        min_rating = int(min_rating)
        products = products.annotate(
            avg_rating=Avg('reviews__rating')
        ).filter(avg_rating__gte=min_rating)

    # Apply sorting
    products = get_sorted_products(products, sort_by)

    # Pagination
    paginator = Paginator(products, 24)
    page_number = request.GET.get('page')
    products_page = paginator.get_page(page_number)

    # Get categories for filter dropdown
    categories = Category.objects.annotate(
        product_count=Count('products')
    ).filter(product_count__gt=0)

    # Get related searches
    related_searches = []
    if query:
        cache_key = f"search_suggestions:{query[:20]}"
        related_searches = cache.get(cache_key)
        if not related_searches:
            # Get popular searches related to this query
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT query, COUNT(*) 
                    FROM store_searchlog 
                    WHERE query %% %s
                    GROUP BY query
                    ORDER BY COUNT(*) DESC
                    LIMIT 5
                """, [query])
                related_searches = [row[0] for row in cursor.fetchall()]
            cache.set(cache_key, related_searches, 3600)

    return render(request, 'store/search/results.html', {
        'products': products_page,
        'query': query,
        'categories': categories,
        'sort_by': sort_by,
        'sort_options': SORT_OPTIONS,
        'max_price': max_price,
        'min_rating': min_rating,
        'in_stock': in_stock,
        'related_searches': related_searches,
    })


@require_GET
def search_suggestions(request):
    query = request.GET.get('q', '').strip()
    suggestions = []

    # Get trending products when no query
    if not query:
        trending = cache.get('trending_products')
        if not trending:
            trending = Product.objects.filter(
                available=True
            ).annotate(
                review_count=Count('reviews')
            ).order_by('-review_count')[:5]
            cache.set('trending_products', trending, 3600)

        return JsonResponse({
            'suggestions': [{
                'section': 'Trending Products',
                'type': 'product',
                'name': p.name,
                'url': p.get_absolute_url(),
                'image': p.image.url if p.image else '',
                'price': str(p.get_display_price()),
                'category': p.category.name
            } for p in trending]
        })

    # Log search query
    if query and len(query) > 2:
        SearchLog.objects.create(
            query=query,
            ip_address=request.META.get('REMOTE_ADDR')
        )

    # Build sections
    sections = []

    # 1. Popular Searches Section
    popular_searches = []
    if len(query) > 3:
        cache_key = f"popular_searches:{query[:20]}"
        popular_searches = cache.get(cache_key)
        if not popular_searches:
            popular_searches = SearchLog.objects.filter(
                query__trigram_similar=query
            ).values('query').annotate(
                count=Count('id')
            ).order_by('-count')[:3]
            popular_searches = [{
                'type': 'search',
                'name': item['query'],
                'url': reverse('store:product_search') + f'?q={item["query"]}'
            } for item in popular_searches]
            cache.set(cache_key, popular_searches, 3600)

    if popular_searches:
        sections.append({
            'name': 'Popular Searches',
            'items': popular_searches
        })

    # 2. Categories Section
    categories = Category.objects.annotate(
        similarity=TrigramSimilarity('name', query)
    ).filter(similarity__gt=0.2).order_by('-similarity')[:2]

    if categories.exists():
        sections.append({
            'name': 'Categories',
            'items': [{
                'type': 'category',
                'name': c.name,
                'url': c.get_absolute_url(),
            } for c in categories]
        })

    # 3. Products Section
    products = Product.objects.annotate(
        similarity=Greatest(
            TrigramSimilarity('name', query),
            TrigramSimilarity('short_description', query),
            TrigramSimilarity('description', query),
            TrigramSimilarity('category__name', query)
        )
    ).filter(
        similarity__gt=SUGGESTION_THRESHOLD,
        available=True
    ).order_by('-similarity')[:8]

    if products.exists():
        sections.append({
            'name': 'Products',
            'items': [{
                'type': 'product',
                'name': p.name,
                'url': p.get_absolute_url(),
                'image': p.image.url if p.image else '',
                'price': str(p.get_display_price()),
                'category': p.category.name
            } for p in products]
        })

    return JsonResponse({'sections': sections})

class ProductSearchView(ListView):
    model = Product
    template_name = 'store/product/search.html'
    paginate_by = 16
    context_object_name = 'products'

    @method_decorator(cache_page(60 * 15))  # Cache for 15 minutes
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get_queryset(self):
        query = self.request.GET.get('q', '').strip()
        if not query:
            return Product.objects.none()

        # Use PostgreSQL full-text search with trigram fallback
        search_query = SearchQuery(query, config='english')

        # Build search vector without 'tags' field
        vector = (
                SearchVector('name', weight='A') +
                SearchVector('short_description', weight='B') +
                SearchVector('description', weight='B') +
                SearchVector('category__name', weight='C')
        )

        # Base queryset with ranking
        products = Product.objects.annotate(
            rank=SearchRank(vector, search_query, weights=SEARCH_WEIGHTS),
            similarity=Greatest(
                TrigramSimilarity('name', query),
                TrigramSimilarity('short_description', query),
                TrigramSimilarity('description', query),
                TrigramSimilarity('category__name', query)
            )
        ).filter(
            (Q(rank__gte=0.1) | Q(similarity__gt=SUGGESTION_THRESHOLD)),
            available=True
        ).select_related('category').order_by('-rank', '-similarity')

        # Apply filters
        return self.apply_filters(products)

    def apply_filters(self, queryset):
        # Category filter
        category_slug = self.request.GET.get('category')
        if category_slug:
            queryset = queryset.filter(category__slug=category_slug)

        # Price filter
        max_price = self.request.GET.get('max_price')
        if max_price and max_price.isdigit():
            queryset = queryset.filter(price__lte=int(max_price))

        # Availability filter
        in_stock = self.request.GET.get('in_stock')
        if in_stock == 'true':
            queryset = queryset.filter(stock__gt=0)

        # Rating filter
        min_rating = self.request.GET.get('min_rating')
        if min_rating and min_rating.isdigit():
            min_rating = int(min_rating)
            queryset = queryset.annotate(
                avg_rating=Coalesce(Avg('reviews__rating'), 0.0)
            ).filter(avg_rating__gte=min_rating)

        # Sort options
        sort_by = self.request.GET.get('sort', '-created')
        return get_sorted_products(queryset, sort_by)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        query = self.request.GET.get('q', '')
        context['query'] = query
        context['sort_options'] = SORT_OPTIONS
        context['sort_by'] = self.request.GET.get('sort', '-created')

        # Add popular search terms to context
        if query:
            cache_key = f"search_suggestions:{query[:20]}"
            suggestions = cache.get(cache_key)
            if not suggestions:
                # Get popular searches related to this query
                with connection.cursor() as cursor:
                    cursor.execute("""
                        SELECT query, COUNT(*) 
                        FROM store_searchlog 
                        WHERE query %% %s
                        GROUP BY query
                        ORDER BY COUNT(*) DESC
                        LIMIT 5
                    """, [query])
                    suggestions = [row[0] for row in cursor.fetchall()]
                cache.set(cache_key, suggestions, 3600)
            context['related_searches'] = suggestions

        return context


def get_sorted_products(queryset, sort_key):
    """Enhanced sorting with annotations for discount percentage"""
    queryset = queryset.annotate(
        avg_rating=Coalesce(Avg('reviews__rating'), 0.0),
        review_count_annotation=Count('reviews'),
    )

    # Only annotate discount_percentage when needed
    if sort_key == 'discount':
        queryset = queryset.annotate(
            discount_percentage=ExpressionWrapper(
                (F('price') - F('discount_price')) / F('price') * 100,
                output_field=DecimalField()
            )
        )

    sort_field = SORT_OPTIONS.get(sort_key, '-created')
    return queryset.order_by(sort_field)




def product_list(request, category_slug=None):
    """Product listing with filtering, sorting, and pagination"""
    category = None

    categories = Category.objects.filter(
        is_active=True
    ).annotate(
        num_products=Count('products', filter=Q(products__available=True))
    ).filter(num_products__gt=0)

    products = Product.objects.filter(
        available=True
    ).select_related('category').prefetch_related('additional_images')

    if category_slug:
        category = get_object_or_404(Category, slug=category_slug, is_active=True)
        products = products.filter(category=category)

    if category_slug:
        category = get_object_or_404(Category, slug=category_slug)
        # Include products from all descendants
        descendants = category.get_descendants(include_self=True)
        products = products.filter(category__in=descendants)

    max_price = request.GET.get('max_price')
    if max_price and max_price.replace('.', '', 1).isdigit():
        products = products.filter(price__lte=float(max_price))

    in_stock = request.GET.get('in_stock')
    if in_stock == 'true':
        products = products.filter(stock__gt=0)

    min_rating = request.GET.get('min_rating')
    if min_rating and min_rating.replace('.', '', 1).isdigit():
        products = products.annotate(
            avg_rating=Coalesce(Avg('reviews__rating'), 0.0)
        ).filter(avg_rating__gte=float(min_rating))

    sort_by = request.GET.get('sort', '-created')
    products = get_sorted_products(products, sort_by)

    paginator = Paginator(products, 24)
    page_number = request.GET.get('page')
    try:
        products_page = paginator.page(page_number)
    except PageNotAnInteger:
        products_page = paginator.page(1)
    except EmptyPage:
        products_page = paginator.page(paginator.num_pages)

    # ✅ Include top-level categories for navigation
    top_level_categories = Category.objects.filter(
        parent=None,
        is_active=True
    ).annotate(
        _product_count_cache=Count('products', filter=Q(products__available=True))
    )

    context = {
        'category': category,
        'categories': categories,
        'top_level_categories': top_level_categories,
        'products': products_page,
        'sort_by': sort_by,
        'sort_options': SORT_OPTIONS,
        'max_price': max_price or "",
        'in_stock': in_stock == 'true',
        'min_rating': min_rating or "",
    }
    return render(request, 'store/product/list.html', context)

def product_detail(request, slug):
    """Optimized product detail view with prefetch_related"""
    product = get_object_or_404(
        Product.objects
        .select_related('category')
        .prefetch_related(
            Prefetch('additional_images', queryset=ProductImage.objects.all().only('image', 'color')),
            'reviews__user'
        ),
        slug=slug,
        available=True
    )

    # Calculate discount percentage
    discount_percentage = product.get_discount_percentage() if product.discount_price else 0

    # Get related products (same category, exclude current product)
    related_products = Product.objects.filter(
        category=product.category,
        available=True
    ).exclude(id=product.id).order_by('?')[:4]  # Random 4 products

    # Handle affiliate link
    affiliate_link = None
    if product.is_dropship:
        affiliate_link = generate_affiliate_link(product.supplier_url)

    if request.method == 'POST' and request.user.is_authenticated:
        review_form = ReviewForm(request.POST)
        if review_form.is_valid():
            if Review.objects.filter(product=product, user=request.user).exists():
                messages.warning(request, 'You already reviewed this product!')
            else:
                review = review_form.save(commit=False)
                review.product = product
                review.user = request.user
                review.save()
                product.update_rating()
                messages.success(request, 'Review submitted!')
                return redirect('store:product_detail', slug=slug)
    else:
        review_form = ReviewForm()

    context = {
        'product': product,
        'related_products': related_products,
        'cart_product_form': CartAddProductForm(),
        'review_form': review_form,
        'discount_percentage': discount_percentage,
        'affiliate_link': affiliate_link,
    }
    return render(request, 'store/product/detail.html', context)


def legacy_product_redirect(request, id, slug):
    """Redirect old product URLs to new slug-only URLs"""
    product = get_object_or_404(Product, id=id)
    return redirect('store:product_detail', slug=product.slug, permanent=True)


def search_suggestions(request):
    query = request.GET.get('q', '').strip()
    suggestions = []

    # Get trending products when no query
    if not query:
        trending = cache.get('trending_products')
        if not trending:
            trending = Product.objects.filter(
                available=True
            ).annotate(
                review_count=Count('reviews')
            ).order_by('-review_count')[:5]
            cache.set('trending_products', trending, 3600)  # Cache for 1 hour

        suggestions = [{
            'type': 'trending',
            'name': p.name,
            'url': p.get_absolute_url(),
            'image': p.image.url if p.image else '',
            'price': str(p.get_display_price()),
            'rating': float(p.rating),
            'category': p.category.name
        } for p in trending]
        return JsonResponse({'suggestions': suggestions})

    # Log search query for analytics
    if query and len(query) > 2:
        from .models import SearchLog
        SearchLog.objects.create(query=query, ip_address=request.META.get('REMOTE_ADDR'))

    # Get products with trigram similarity
    products = Product.objects.annotate(
        similarity=Greatest(
            TrigramSimilarity('name', query),
            TrigramSimilarity('short_description', query),
            TrigramSimilarity('description', query),
            TrigramSimilarity('category__name', query)
        )
    ).filter(
        similarity__gt=SUGGESTION_THRESHOLD,
        available=True
    ).order_by('-similarity')[:8]

    # Get categories
    categories = Category.objects.annotate(
        similarity=TrigramSimilarity('name', query)
    ).filter(
        similarity__gt=0.2
    ).order_by('-similarity')[:2]  # Reduced from 3 to 2

    # Get popular searches
    popular_searches = []
    if len(query) > 3:
        cache_key = f"popular_searches:{query[:20]}"
        popular_searches = cache.get(cache_key)
        if not popular_searches:
            # Get popular searches from the database
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT query, COUNT(*) 
                    FROM store_searchlog 
                    WHERE query %% %s
                    GROUP BY query
                    ORDER BY COUNT(*) DESC
                    LIMIT 3
                """, [query])
                popular_searches = [{'type': 'search', 'name': row[0]} for row in cursor.fetchall()]
            cache.set(cache_key, popular_searches, 3600)

    # Build suggestions with type information
    for p in products:
        suggestions.append({
            'type': 'product',
            'name': p.name,
            'url': p.get_absolute_url(),
            'price': str(p.get_display_price()),
            'rating': float(p.rating),
            'category': p.category.name
        })

    for c in categories:
        suggestions.append({
            'type': 'category',
            'name': c.name,
            'url': c.get_absolute_url(),
        })

    # Add popular searches to suggestions
    suggestions.extend(popular_searches)

    return JsonResponse({'suggestions': suggestions})


def submit_review(request, slug):
    """Handle review submissions"""
    if not request.user.is_authenticated:
        messages.error(request, 'Please log in to submit a review.')
        return redirect('login')

    product = get_object_or_404(Product, slug=slug)

    if request.method == 'POST':
        form = ReviewForm(request.POST)
        if form.is_valid():
            if Review.objects.filter(product=product, user=request.user).exists():
                messages.warning(request, 'You have already reviewed this product!')
            else:
                review = form.save(commit=False)
                review.product = product
                review.user = request.user
                review.save()
                product.update_rating()
                messages.success(request, 'Thank you for your review!')
        else:  # Add form error handling
            messages.error(request, 'Invalid review submission. Please check your input.')

    return redirect('store:product_detail', slug=product.slug)


def product_categories(request):
    categories = Category.objects.annotate(
        num_products=Count('products')
    )[:5]

    total_products = Product.objects.filter(available=True).count()

    context = {
        'categories': categories,
        'total_products': total_products,
    }
    return render(request, 'store/product/categories.html', context)


logger = logging.getLogger('newsletter')


def create_confirmation_email_content(request: HttpRequest, subscription: NewsletterSubscription) -> tuple[str, str]:
    confirmation_link = request.build_absolute_uri(
        reverse('store:confirm_subscription', args=[subscription.confirmation_token]))
    unsubscribe_link = request.build_absolute_uri(
        reverse('store:unsubscribe', args=[subscription.unsubscribe_token]))
    privacy_policy_link = request.build_absolute_uri(reverse('users:privacy'))

    plaintext_message = f"""Please confirm your subscription by clicking:
{confirmation_link}

If you didn't request this, you can unsubscribe here:
{unsubscribe_link}

Privacy Policy: {privacy_policy_link}
IP Address: {subscription.ip_address}
Signup Date: {subscription.created_at}
"""

    html_content = f"""
    <h2>Almost there!</h2>
    <p>Click below to confirm your subscription:</p>
    <a href="{confirmation_link}" style="...">Confirm Subscription</a>
    <p>Or copy this link to your browser:<br><code>{confirmation_link}</code></p>
    <p style="margin-top: 20px;">
        <small>
            If you didn't request this, please 
            <a href="{unsubscribe_link}">unsubscribe here</a>.<br>
            IP Address: {subscription.ip_address}<br>
            Signup Date: {subscription.created_at}<br>
            <a href="{privacy_policy_link}">Privacy Policy</a>
        </small>
    </p>
    """
    return plaintext_message, html_content


@require_POST
def subscribe(request):
    email = request.POST.get('email', '').strip()

    try:
        validate_email(email)

        # Check existing subscriptions
        existing = NewsletterSubscription.objects.filter(email=email).first()
        if existing:
            if existing.confirmed and not existing.unsubscribed:
                messages.info(request, "This email is already subscribed!")
                return redirect('store:home')
            messages.warning(request, "Please check your email to confirm subscription!")
            return redirect('store:home')

        # Create new subscription
        subscription = NewsletterSubscription(
            email=email,
            ip_address=request.META.get('REMOTE_ADDR'),
            source_url=request.META.get('HTTP_REFERER')
        )
        subscription.generate_tokens()
        subscription.confirmation_sent = timezone.now()
        subscription.save()

        # Create email content
        plaintext, html = create_confirmation_email_content(request, subscription)

        # Send email
        send_email_async(
            "Confirm newsletter subscription",
            plaintext,
            email,
            html_message=html
        )

        logger.info(f"Subscription initiated for {email}")
        messages.success(request, "Confirmation email sent! Please check your inbox.")
        return redirect('store:home')

    except ValidationError:
        logger.warning(f"Invalid email attempt: {email}")
        messages.error(request, "Please enter a valid email address.")
    except Exception as e:
        logger.error(f"Subscription error for {email}: {str(e)}", exc_info=True)
        messages.error(request, "Subscription failed. Please try again later.")

    return redirect('store:home')


def confirm_subscription(request, token):
    try:
        subscription = NewsletterSubscription.objects.get(
            confirmation_token=token,
            confirmed=False,
            unsubscribed=False
        )

        if (timezone.now() - subscription.confirmation_sent).days > 1:
            subscription.delete()
            logger.info(f"Expired subscription attempt: {token}")
            messages.error(request, "Confirmation link has expired.")
            return redirect('store:home')

        subscription.confirmed = True
        subscription.confirmed_at = timezone.now()
        subscription.save()

        logger.info(f"Subscription confirmed: {subscription.email}")
        messages.success(request, "Subscription confirmed! Welcome to our newsletter.")

    except NewsletterSubscription.DoesNotExist:
        logger.warning(f"Invalid confirmation token: {token}")
        messages.error(request, "Invalid confirmation link.")

    return redirect('store:home')


def unsubscribe(request, token):
    try:
        subscription = NewsletterSubscription.objects.get(
            unsubscribe_token=token,
            unsubscribed=False
        )
        subscription.unsubscribed = True
        subscription.save()

        logger.info(f"Unsubscribed: {subscription.email}")
        messages.success(request, "You've been unsubscribed successfully.")
    except NewsletterSubscription.DoesNotExist:
        logger.warning(f"Invalid unsubscribe token: {token}")
        messages.error(request, "Invalid unsubscribe link.")

    return render(request, 'store/newsletter/unsubscribe.html', {
        'success': subscription is not None
    })


class EmailPreviewView(TemplateView):
    template_name = 'store/newsletter/emails/confirmation_email.html'

    def get_context_data(self, **kwargs):
        return {
            'confirmation_url': '#',
            'unsubscribe_url': '#',
            'privacy_url': '#',
            'email': 'test@example.com',
            'ip_address': '127.0.0.1',
            'timestamp': timezone.now()
        }


class TemplateTestView(TemplateView):
    def get_template_names(self):
        return self.kwargs['template']

    def get_context_data(self, **kwargs):
        return {
            'confirmation_url': 'https://example.com/confirm/',
            'unsubscribe_url': 'https://example.com/unsubscribe/',
            'privacy_url': reverse('users:privacy'),
            'email': 'test@example.com',
            'ip_address': '127.0.0.1',
            'timestamp': timezone.now()
        }


def contact(request):
    return render(request, 'store/contact.html', {'title': 'Contact Us'})


def faq(request):
    return render(request, 'store/faq.html', {'title': 'FAQs'})


def shipping(request):
    return render(request, 'store/shipping.html', {'title': 'Shipping Policy'})


def returns(request):
    return render(request, 'store/returns.html', {'title': 'Return Policy'})


def warranty(request):
    return render(request, 'store/warranty.html', {'title': 'Warranty'})


def tracking(request):
    return render(request, 'store/tracking.html', {'title': 'Track Order'})


def privacy(request):
    return render(request, 'store/privacy.html', {'title': 'Privacy Policy'})


def terms(request):
    return render(request, 'store/terms.html', {'title': 'Terms of Service'})


def cookies(request):
    return render(request, 'store/cookies.html', {'title': 'Cookie Policy'})


def accessibility(request):
    return render(request, 'store/accessibility.html', {'title': 'Accessibility'})


def sitemap(request):
    return render(request, 'store/sitemap.html', {'title': 'Sitemap'})


# In views.py
def some_view(request):
    print(CATEGORIES["🎮 Game Controllers & Input Devices"])


# In templates (via context)
def category_list(request):
    return render(request, 'categories.html', {'categories': CATEGORIES})


def is_staff(user):
    return user.is_authenticated and user.is_staff

@login_required(login_url='/accounts/login/')
@user_passes_test(is_staff, login_url='/accounts/login/')
def add_product(request):
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES)
        image_formset = ProductImageFormSet(request.POST, request.FILES, prefix='images')

        if form.is_valid() and image_formset.is_valid():
            product = form.save()
            image_formset.instance = product
            image_formset.save()
            messages.success(request, 'Product added successfully!')
            return redirect('store:product_dashboard')
    else:
        form = ProductForm()
        image_formset = ProductImageFormSet(prefix='images', queryset=ProductImage.objects.none())

    return render(request, 'store/dashboard/add_product.html', {
        'form': form,
        'image_formset': image_formset
    })


@login_required(login_url='/accounts/login/')
@user_passes_test(is_staff, login_url='/accounts/login/')
def product_dashboard(request):
    products = Product.objects.select_related('category').order_by('-created')
    return render(request, 'store/dashboard/product_dashboard.html', {'products': products})


@login_required(login_url='/accounts/login/')
@user_passes_test(is_staff, login_url='/accounts/login/')
def edit_product(request, slug):
    product = get_object_or_404(Product, slug=slug)

    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES, instance=product)
        image_formset = ProductImageFormSet(
            request.POST,
            request.FILES,
            prefix='images',
            instance=product
        )

        if form.is_valid() and image_formset.is_valid():
            form.save()
            image_formset.save()

            messages.success(request, f'Product "{product.name}" updated successfully!')
            return redirect('store:product_detail', slug=product.slug)
    else:
        form = ProductForm(instance=product)
        image_formset = ProductImageFormSet(prefix='images', instance=product)

    return render(request, 'store/dashboard/add_product.html', {
        'form': form,
        'image_formset': image_formset,
        'product': product
    })


@login_required(login_url='/accounts/login/')
@user_passes_test(is_staff, login_url='/accounts/login/')
def delete_product(request, slug):
    product = get_object_or_404(Product, slug=slug)
    if request.method == 'POST':
        product_name = product.name
        product.delete()
        messages.success(request, f'Product "{product_name}" deleted successfully!')
        return redirect('store:product_dashboard')

    return render(request, 'store/dashboard/delete_product.html', {'product': product})


def custom_404(request, exception):
    return render(request, '404.html', status=404)


def custom_500(request):
    return render(request, '500.html', status=500)


@require_POST
def search_analytics(request):
    data = json.loads(request.body)
    query = data.get('query', '')[:255]
    results_count = data.get('results_count', 0)

    if query:
        SearchLog.objects.create(
            query=query,
            results_count=results_count,
            ip_address=request.META.get('REMOTE_ADDR')
        )
        return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'invalid'}, status=400)


@login_required
@user_passes_test(lambda u: u.is_staff)
def import_products(request):
    if request.method == 'POST':
        form = ImportProductsForm(request.POST)
        if form.is_valid():
            url = form.cleaned_data['url']
            category = form.cleaned_data['category']

            product, message = import_aliexpress_product(url, category.slug)

            if product:
                messages.success(request, f'Successfully imported: {product.name}')
                return redirect('store:edit_product', slug=product.slug)
            else:
                messages.error(request, f'Import failed: {message}')
    else:
        form = ImportProductsForm()

    return render(request, 'store/dashboard/import_products.html', {
        'form': form,
        'title': 'Import AliExpress Products'
    })