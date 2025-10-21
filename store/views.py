# store/views.py
from store.utils.search import apply_search_filter
from django.core.serializers.json import DjangoJSONEncoder
from .utils.sorting import get_sorted_products
from store.constants import SORT_OPTIONS
from .utils.filters import apply_product_filters
from django.template.loader import render_to_string
from django.http import HttpResponse
from store.aliexpress import import_aliexpress_product, generate_affiliate_link
from .forms import ImportProductsForm, ReviewForm, ProductForm, ProductImageFormSet
from django.shortcuts import render, get_object_or_404, redirect
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Avg, Q, Count, F, ExpressionWrapper, DecimalField, Prefetch
from django.views.generic import TemplateView, ListView
from .models import Category, Product, Review, NewsletterSubscription, ProductImage, SearchLog, StockNotification
from cart.forms import CartAddProductForm
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.contrib import messages
from django.views.decorators.http import require_POST, require_GET
from django.utils import timezone
from .utils.send_email_async import send_email_async
import logging
from django.http import HttpRequest, JsonResponse
from django.urls import reverse
from django.db.models.functions import Coalesce, Greatest
from store.constants import CATEGORIES
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank, TrigramSimilarity
from django.core.cache import cache
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.db import connection
import json

logger = logging.getLogger('newsletter')

SEARCH_WEIGHTS = [0.1, 0.2, 0.4, 1.0]  # D, C, B, A weights
SUGGESTION_THRESHOLD = 0.15
TRENDING_CACHE_KEY = 'trending_products'
TRENDING_CACHE_TIMEOUT = 3600  # seconds

# ----- Search Views ----- #
@require_GET
def product_search(request):
    """
    Simple redirecting search function for non-class-based requests.
    The urls.py uses ProductSearchView for full search.
    This view remains for backward compatibility if used elsewhere.
    """
    query = request.GET.get('q', '').strip()
    if not query:
        return redirect('store:product_list')

    # For compatibility, reuse ProductSearchView logic via redirect to class-based view route
    # Include query params so the CBV can handle presentation & paging
    url = reverse('store:product_search') + f'?q={query}'
    # copy other known params if present (page, sort, filters)
    for param in ['page', 'sort', 'max_price', 'min_rating', 'in_stock', 'category']:
        val = request.GET.get(param)
        if val:
            url += f'&{param}={val}'
    return redirect(url)


class ProductSearchView(ListView):
    model = Product
    template_name = 'store/product/search.html'
    paginate_by = 16
    context_object_name = 'products'

    @method_decorator(cache_page(60 * 15))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get_queryset(self):
        query = self.request.GET.get('q', '').strip()
        if not query:
            return Product.objects.none()

        # Build search query & vector (we rely on denormalized search fields on Product)
        search_query = SearchQuery(query, config='english')

        # Use fields that map to stored search_vector and trigram columns
        vector = (
            SearchVector('search_name', weight='A') +
            SearchVector('search_description', weight='B') +
            SearchVector('search_category', weight='C') +
            SearchVector('search_brand', weight='B') +
            SearchVector('search_supplier', weight='C')
        )

        products = Product.objects.annotate(
            rank=SearchRank(vector, search_query, weights=[0.1, 0.2, 0.4, 1.0]),
            similarity=Greatest(
                TrigramSimilarity('name', query),
                TrigramSimilarity('short_description', query),
                TrigramSimilarity('description', query),
                TrigramSimilarity('search_category', query),
                TrigramSimilarity('search_brand', query),
                TrigramSimilarity('search_supplier', query),
            ),
            # ✅ Use cached review_count to boost popular products
            popularity_score=F('review_count'),

            # ✅ Normalize rating from 0–5 into a 0–1 scale
            quality_score=ExpressionWrapper(
                Coalesce(F('rating'), 0) / 5.0,
                output_field=DecimalField(max_digits=4, decimal_places=2)
            ),

            # ✅ Final boosted search score
            final_score=ExpressionWrapper(
                (F('rank') * 0.7) +  # base relevance
                (F('similarity') * 0.5) +  # trigram match
                (F('popularity_score') * 0.03) +  # boost by review count
                (F('quality_score') * 0.2),  # boost by rating
                output_field=DecimalField(max_digits=6, decimal_places=2)
            )
        ).filter(
            (Q(rank__gte=0.1) | Q(similarity__gt=0.15)),
            available=True
        ).select_related('category', 'brand', 'supplier').order_by('-final_score')


        # Apply same request filters (you previously had apply_product_filters helper;
        # if you use a helper, call it here - else keep inline filters)
        # Example inline filters:
        req = self.request
        category_slug = req.GET.get('category')
        if category_slug:
            products = products.filter(category__slug=category_slug)

        max_price = req.GET.get('max_price')
        if max_price and max_price.replace('.', '', 1).isdigit():
            products = products.filter(price__lte=float(max_price))

        in_stock = req.GET.get('in_stock')
        if in_stock == 'true':
            products = products.filter(stock__gt=0)

        min_rating = req.GET.get('min_rating')
        if min_rating and min_rating.replace('.', '', 1).isdigit():
            products = products.annotate(
                avg_rating=Coalesce(Avg('reviews__rating'), 0.0)
            ).filter(avg_rating__gte=float(min_rating))

        # brand filter (now safe because brand is a FK)
        brand_slug = req.GET.get('brand')
        if brand_slug:
            products = products.filter(brand__slug=brand_slug)

        sort_by = self.request.GET.get('sort', '-created')
        return get_sorted_products(products, sort_by)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        query = self.request.GET.get('q', '')
        context.update({
            'query': query,
            'sort_options': SORT_OPTIONS,
            'sort_by': self.request.GET.get('sort', '-created'),
        })

        # related searches (cached) - keep your existing SQL trigram approach
        if query:
            cache_key = f"search_suggestions:{query[:20]}"
            suggestions = cache.get(cache_key)
            if not suggestions:
                try:
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
                except Exception:
                    suggestions = []
            context['related_searches'] = suggestions
        return context

    def render_to_response(self, context, **response_kwargs):
        request = self.request
        is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest'
        if is_ajax:
            html = render_to_string('store/product/_results_grid.html', context=context, request=request)
            return HttpResponse(html)
        return super().render_to_response(context, **response_kwargs)


@require_GET
def search_suggestions(request):
    """
    Single optimized suggestions endpoint returning JSON sections.
    """
    query = request.GET.get('q', '').strip()
    sections = []

    trending = cache.get(TRENDING_CACHE_KEY)
    if not trending:
        trending = list(Product.objects.filter(available=True).annotate(review_count=Count('reviews')).order_by('-review_count')[:6])
        cache.set(TRENDING_CACHE_KEY, trending, TRENDING_CACHE_TIMEOUT)

    if not query:
        sections.append({
            'name': 'Trending Products',
            'items': [{
                'type': 'product',
                'name': p.name,
                'url': p.get_absolute_url(),
                'image': p.image.url if p.image else '',
                'price': str(p.get_display_price()),
                'category': p.category.name if p.category else ''
            } for p in trending]
        })
        return JsonResponse({'sections': sections})

    # log (best-effort)
    if len(query) > 2:
        try:
            SearchLog.objects.create(query=query, ip_address=request.META.get('REMOTE_ADDR'))
        except Exception:
            logger.exception("Failed to log search query")

    categories = list(Category.objects.annotate(similarity=TrigramSimilarity('name', query)).filter(similarity__gt=0.2).order_by('-similarity')[:3])
    if categories:
        sections.append({
            'name': 'Categories',
            'items': [{'type': 'category', 'name': c.name, 'url': c.get_absolute_url()} for c in categories]
        })

    product_candidates = list(Product.objects.annotate(similarity=Greatest(
        TrigramSimilarity('name', query),
        TrigramSimilarity('short_description', query),
        TrigramSimilarity('description', query),
        TrigramSimilarity('category__name', query)
    )).filter(similarity__gt=SUGGESTION_THRESHOLD, available=True).order_by('-similarity')[:8])

    if product_candidates:
        sections.append({
            'name': 'Products',
            'items': [{
                'type': 'product',
                'name': p.name,
                'url': p.get_absolute_url(),
                'image': p.image.url if p.image else '',
                'price': str(p.get_display_price()),
                'category': p.category.name if p.category else ''
            } for p in product_candidates]
        })

    # Popular searches
    popular_searches = []
    if len(query) > 3:
        cache_key = f"popular_searches:{query[:20]}"
        popular_searches = cache.get(cache_key)
        if not popular_searches:
            try:
                with connection.cursor() as cursor:
                    cursor.execute("""
                        SELECT query, COUNT(*) 
                        FROM store_searchlog 
                        WHERE query %% %s
                        GROUP BY query
                        ORDER BY COUNT(*) DESC
                        LIMIT 5
                    """, [query])
                    popular_searches = [{'type': 'search', 'name': row[0], 'url': reverse('store:product_search') + f'?q={row[0]}'}
                                       for row in cursor.fetchall()]
                cache.set(cache_key, popular_searches, 3600)
            except Exception:
                popular_searches = []
    if popular_searches:
        sections.append({'name': 'Popular Searches', 'items': popular_searches})

    return JsonResponse({'sections': sections})


# ----- Product listing & detail views ----- #
@require_GET
def product_list(request, category_slug=None):
    # categories for sidebar
    categories = Category.objects.filter(is_active=True).annotate(
        num_products=Count('products', filter=Q(products__available=True))
    ).filter(num_products__gt=0)

    products = Product.objects.filter(available=True).select_related('category').prefetch_related('additional_images')

    category = None
    if category_slug:
        category = get_object_or_404(Category, slug=category_slug, is_active=True)
        try:
            descendants = category.get_descendants(include_self=True)
            products = products.filter(category__in=descendants)
        except Exception:
            products = products.filter(category=category)

    products = apply_product_filters(request, products)

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

    # top level categories
    top_level_categories = Category.objects.filter(parent=None, is_active=True).annotate(
        _product_count_cache=Count('products', filter=Q(products__available=True))
    )

    context = {
        'category': category,
        'categories': categories,
        'top_level_categories': top_level_categories,
        'products': products_page,
        'sort_by': sort_by,
        'sort_options': SORT_OPTIONS,
        'max_price': request.GET.get('max_price', ''),
        'in_stock': request.GET.get('in_stock') == 'true',
        'min_rating': request.GET.get('min_rating', ''),
    }
    return render(request, 'store/product/list.html', context)


def product_detail(request, slug):
    # Updated prefetch to include variants and approved reviews with user
    product = get_object_or_404(Product.objects.select_related('category').prefetch_related(
        Prefetch('additional_images', queryset=ProductImage.objects.all().only('image', 'color')),
        Prefetch('reviews', queryset=Review.objects.filter(approved=True).select_related('user')),
        'variants'
    ), slug=slug, available=True)

    discount_percentage = product.get_discount_percentage() if product.discount_price else 0
    related_products = Product.objects.filter(category=product.category, available=True).exclude(id=product.id).order_by('?')[:4]

    # Removed the dead POST logic for reviews, as it's handled by submit_review view

    # Correctly generate affiliate link
    affiliate_link = None
    if product.is_dropship and product.supplier_url:
        try:
            # Assumes supplier_url is the one to use
            affiliate_link = generate_affiliate_link(product.supplier_url)
        except Exception:
            logger.warning(f"Could not generate affiliate link for {product.slug}")

    # Serialize variants for JavaScript
    variants_data = list(product.variants.all().values(
        'id', 'size', 'color', 'price', 'quantity'
    ))
    # Create a structure that groups variants by attribute (e.g., color)
    # This is needed for the <select> or swatch logic
    variants_by_color = {}
    variants_by_size = {}
    for v in variants_data:
        if v['color']:
            variants_by_color.setdefault(v['color'], []).append(v)
        if v['size']:
            variants_by_size.setdefault(v['size'], []).append(v)

    variants_json = json.dumps(variants_data, cls=DjangoJSONEncoder)

    context = {
        'product': product,
        'related_products': related_products,
        'cart_product_form': CartAddProductForm(),
        'review_form': ReviewForm(), # Always pass an empty form
        'discount_percentage': discount_percentage,
        'affiliate_link': affiliate_link, # Now correctly populated
        'variants_json': variants_json, # Pass JSON to template
        'variant_colors': list(variants_by_color.keys()), # Pass unique colors
        'variant_sizes': list(variants_by_size.keys()), # Pass unique sizes
    }
    return render(request, 'store/product/detail.html', context)


@require_POST
@login_required
def mark_review_helpful(request, review_id):
    """
    Handles AJAX request to mark a review as helpful.
    """
    review = get_object_or_404(Review, id=review_id, approved=True)

    # This is a simple implementation. A real one would use a
    # ManyToManyField to track *who* voted to prevent multiple votes.
    review.helpful_count = F('helpful_count') + 1
    review.save(update_fields=['helpful_count'])
    review.refresh_from_db()

    return JsonResponse({'success': True, 'new_count': review.helpful_count})


@require_POST
def stock_notification(request):
    """
    Handles AJAX request to create a stock notification.
    """
    try:
        data = json.loads(request.body)
        product_id = data.get('product_id')
        email = data.get('email', '').strip()

        if not product_id or not email:
            return JsonResponse({'success': False, 'message': 'Missing data.'}, status=400)

        validate_email(email)  # Validate email format

        product = get_object_or_404(Product, id=product_id)

        # Create notification, or ignore if it already exists
        StockNotification.objects.get_or_create(product=product, email=email)

        return JsonResponse({'success': True, 'message': 'You will be notified!'})

    except ValidationError:
        return JsonResponse({'success': False, 'message': 'Invalid email address.'}, status=400)
    except Exception as e:
        logger.error(f"Stock notification error: {e}")
        return JsonResponse({'success': False, 'message': 'An error occurred.'}, status=500)


@login_required
def submit_review(request, slug):
    if request.method != 'POST':
        return redirect('store:product_detail', slug=slug)
    product = get_object_or_404(Product, slug=slug)
    try:
        form = ReviewForm(request.POST)
        if form.is_valid():
            review, created = Review.objects.update_or_create(
                product=product,
                user=request.user,
                defaults={
                    'rating': form.cleaned_data.get('rating'),
                    'title': form.cleaned_data.get('title', '') or '',
                    'comment': form.cleaned_data.get('comment', '') or '',
                    'approved': True,
                }
            )
            messages.success(request, 'Thank you! Your review was submitted.')
        else:
            messages.error(request, 'Invalid review submission. Please check your input.')
    except Exception:
        messages.error(request, 'Could not save your review. Try again later.')
    return redirect('store:product_detail', slug=slug)




def legacy_product_redirect(request, id, slug):
    product = get_object_or_404(Product, id=id)
    return redirect('store:product_detail', slug=product.slug, permanent=True)


# ----- Misc pages & utilities ----- #
def product_categories(request):
    categories = Category.objects.annotate(num_products=Count('products'))[:5]
    total_products = Product.objects.filter(available=True).count()
    context = {'categories': categories, 'total_products': total_products}
    return render(request, 'store/product/categories.html', context)


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
    <a href="{confirmation_link}" style="display:inline-block;padding:12px 20px;background:#2563eb;color:#fff;border-radius:8px;text-decoration:none;">Confirm Subscription</a>
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

        existing = NewsletterSubscription.objects.filter(email=email).first()
        if existing:
            if existing.confirmed and not existing.unsubscribed:
                messages.info(request, "This email is already subscribed!")
                return redirect('store:home')
            messages.warning(request, "Please check your email to confirm subscription!")
            return redirect('store:home')

        subscription = NewsletterSubscription(
            email=email,
            ip_address=request.META.get('REMOTE_ADDR'),
            source_url=request.META.get('HTTP_REFERER')
        )
        subscription.generate_tokens()
        subscription.confirmation_sent = timezone.now()
        subscription.save()

        plaintext, html = create_confirmation_email_content(request, subscription)

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
    subscription = None
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


def some_view(request):
    # debug helper - prints a category from constants
    try:
        print(CATEGORIES.get("🎮 Game Controllers & Input Devices"))
    except Exception:
        pass
    return render(request, 'store/index.html')


@login_required(login_url='/accounts/login/')
@user_passes_test(lambda u: u.is_staff, login_url='/accounts/login/')
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
@user_passes_test(lambda u: u.is_staff, login_url='/accounts/login/')
def product_dashboard(request):
    products = Product.objects.select_related('category').order_by('-created')
    return render(request, 'store/dashboard/product_dashboard.html', {'products': products})


@login_required(login_url='/accounts/login/')
@user_passes_test(lambda u: u.is_staff, login_url='/accounts/login/')
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
            messages.success(request, f'Product \"{product.name}\" updated successfully!')
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
@user_passes_test(lambda u: u.is_staff, login_url='/accounts/login/')
def delete_product(request, slug):
    product = get_object_or_404(Product, slug=slug)
    if request.method == 'POST':
        product_name = product.name
        product.delete()
        messages.success(request, f'Product \"{product_name}\" deleted successfully!')
        return redirect('store:product_dashboard')

    return render(request, 'store/dashboard/delete_product.html', {'product': product})


def custom_404(request, exception):
    return render(request, '404.html', status=404)


def custom_500(request):
    return render(request, '500.html', status=500)


@require_POST
def search_analytics(request):
    data = json.loads(request.body or '{}')
    query = data.get('query', '')[:255]
    results_count = data.get('results_count', 0)
    if query:
        try:
            SearchLog.objects.create(query=query, results_count=results_count, ip_address=request.META.get('REMOTE_ADDR'))
            return JsonResponse({'status': 'success'})
        except Exception:
            logger.exception("Failed to save search analytics")
            return JsonResponse({'status': 'error'}, status=500)
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
    return render(request, 'store/dashboard/import_products.html', {'form': form, 'title': 'Import AliExpress Products'})