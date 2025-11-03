# store/views.py - FIXED VERSION
from functools import wraps
from django.contrib.auth.views import redirect_to_login
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
from .models import Category, Product, Review, NewsletterSubscription, ProductImage, SearchLog, StockNotification, \
    Brand, Supplier
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


def ajax_login_required(view_func):
    """Custom decorator to return JSON 401 for AJAX requests instead of redirecting."""
    @wraps(view_func)
    def wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse(
                    {'success': False, 'message': 'You need to log in to vote helpful reviews.'},
                    status=401
                )
            return redirect_to_login(request.get_full_path())
        return view_func(request, *args, **kwargs)
    return wrapped_view

# ----- Search Views ----- #
@require_GET
def product_search(request):
    """
    Simple redirecting search function for non-class-based requests.
    """
    query = request.GET.get('q', '').strip()
    if not query:
        return redirect('store:product_list')

    url = reverse('store:product_search') + f'?q={query}'
    for param in ['page', 'sort', 'max_price', 'min_rating', 'in_stock', 'category', 'brand', 'supplier']:
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
        query = self.request.GET.get('q', '')
        sort_key = self.request.GET.get('sort', 'relevance')

        # 1. Start with base products
        products = Product.objects.select_related(
            'category', 'brand', 'supplier'
        ).prefetch_related('additional_images')

        # 2. Apply full-text search
        if query:
            # This annotates rank and similarity
            products = apply_search_filter(products, query)
        else:
            # ✅ FIX: For empty queries, annotate with default values
            # This prevents "Cannot resolve keyword 'rank'" error
            from django.db.models import Value, FloatField
            products = products.annotate(
                rank=Value(0.0, output_field=FloatField()),
                similarity=Value(0.0, output_field=FloatField())
            ).filter(available=True)

        # 3. Apply standard filters (price, brand, category, etc.)
        products = apply_product_filters(self.request, products)

        # 4. Apply sorting
        # Now rank and similarity are guaranteed to exist
        return get_sorted_products(products, sort_key, is_search=True)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        query = self.request.GET.get('q', '')
        sort_key = self.request.GET.get('sort', 'relevance')

        context['query'] = query
        context['sort_by'] = sort_key
        context['sort_options'] = SORT_OPTIONS

        # Facet counting
        paginator, page, queryset, is_paginated = self.paginate_queryset(
            self.get_queryset(),
            self.get_paginate_by(self.get_queryset())
        )

        product_ids = list(queryset.values_list('id', flat=True))

        brands = Brand.objects.filter(
            products__id__in=product_ids
        ).annotate(
            product_count=Count('products__id', distinct=True)
        ).order_by('-product_count', 'name')

        suppliers = Supplier.objects.filter(
            products__id__in=product_ids
        ).annotate(
            product_count=Count('products__id', distinct=True)
        ).order_by('-product_count', 'name')

        context['brands'] = brands
        context['suppliers'] = suppliers

        # Pass filter values back to template
        context['max_price'] = self.request.GET.get('max_price', '')
        context['in_stock'] = self.request.GET.get('in_stock') == 'true'
        context['min_rating'] = self.request.GET.get('min_rating', '')
        context['selected_brand'] = self.request.GET.get('brand', '')
        context['selected_supplier'] = self.request.GET.get('supplier', '')
        context['on_sale'] = self.request.GET.get('on_sale') == 'true'  # ✅ ADD THIS if not present

        return context

    def render_to_response(self, context, **response_kwargs):
        request = self.request
        is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest'
        is_htmx = request.headers.get('HX-Request') == 'true'

        if is_ajax or is_htmx:
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
        trending = list(Product.objects.filter(available=True).order_by('-review_count')[:6])
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

    if len(query) > 2:
        try:
            SearchLog.objects.create(query=query, ip_address=request.META.get('REMOTE_ADDR'))
        except Exception:
            logger.exception("Failed to log search query")

    categories = list(Category.objects.annotate(
        similarity=TrigramSimilarity('name', query)
    ).filter(similarity__gt=0.2).order_by('-similarity')[:3])

    if categories:
        sections.append({
            'name': 'Categories',
            'items': [{'type': 'category', 'name': c.name, 'url': c.get_absolute_url()} for c in categories]
        })

    product_candidates = list(Product.objects.annotate(
        similarity=Greatest(
            TrigramSimilarity('name', query),
            TrigramSimilarity('short_description', query),
            TrigramSimilarity('description', query),
            TrigramSimilarity('search_category', query)
        )
    ).filter(similarity__gt=SUGGESTION_THRESHOLD, available=True).order_by('-similarity')[:8])

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
                                   ORDER BY COUNT (*) DESC
                                       LIMIT 5
                                   """, [query])
                    popular_searches = [
                        {'type': 'search', 'name': row[0], 'url': reverse('store:product_search') + f'?q={row[0]}'}
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
    categories = Category.objects.filter(is_active=True).annotate(
        num_products=Count('products', filter=Q(products__available=True))
    ).filter(num_products__gt=0)

    # Handle category from query params (HTMX form) or URL
    category_slug_from_get = request.GET.get('category')
    if category_slug_from_get:
        category_slug = category_slug_from_get
    elif category_slug_from_get == '':
        category_slug = None

    products = Product.objects.filter(available=True).select_related(
        'category', 'brand', 'supplier'
    ).prefetch_related('additional_images')

    category = None
    if category_slug:
        category = get_object_or_404(Category, slug=category_slug, is_active=True)
        try:
            descendants = category.get_descendants(include_self=True)
            products = products.filter(category__in=descendants)
        except Exception:
            products = products.filter(category=category)

    products = apply_product_filters(request, products)

    sort_key = request.GET.get('sort', 'newest')
    sort_option = SORT_OPTIONS.get(sort_key, SORT_OPTIONS['newest'])

    # ✅ --- CORRECTED LINE ---
    # Pass the `sort_key` (e.g., 'newest') to the sorting function,
    # not the `sort_option['field']` (e.g., '-created').
    products = get_sorted_products(products, sort_key, is_search=False)
    # --- END CORRECTION ---

    # Facet counting
    product_ids = list(products.values_list('id', flat=True))
    brands = Brand.objects.filter(
        products__id__in=product_ids
    ).annotate(
        product_count=Count('products__id', distinct=True)
    ).order_by('-product_count', 'name')

    suppliers = Supplier.objects.filter(
        products__id__in=product_ids
    ).annotate(
        product_count=Count('products__id', distinct=True)
    ).order_by('-product_count', 'name')

    paginator = Paginator(products, 24)
    page_number = request.GET.get('page')
    try:
        products_page = paginator.page(page_number)
    except PageNotAnInteger:
        products_page = paginator.page(1)
    except EmptyPage:
        products_page = paginator.page(paginator.num_pages)

    top_level_categories = Category.objects.filter(parent=None, is_active=True).annotate(
        _product_count_cache=Count('products', filter=Q(products__available=True))
    )

    context = {
        'category': category,
        'categories': categories,
        'top_level_categories': top_level_categories,
        'products': products_page,
        'sort_by': sort_key,
        'sort_options': SORT_OPTIONS,
        'max_price': request.GET.get('max_price', ''),
        'in_stock': request.GET.get('in_stock') == 'true',
        'min_rating': request.GET.get('min_rating', ''),
        'brands': brands,
        'suppliers': suppliers,
        'selected_brand': request.GET.get('brand', ''),
        'selected_supplier': request.GET.get('supplier', ''),
        'on_sale': request.GET.get('on_sale') == 'true',  # ✅ ADD THIS LINE
    }

    # Handle HTMX requests
    is_htmx = request.headers.get('HX-Request') == 'true'
    if is_htmx:
        return render(request, 'store/product/_results_grid.html', {
            'products': products_page,
        })

    return render(request, 'store/product/list.html', context)




def product_detail(request, slug):
    product = get_object_or_404(
        Product.objects.select_related('category', 'brand', 'supplier').prefetch_related(
            Prefetch('additional_images', queryset=ProductImage.objects.all().only('image', 'color')),
            Prefetch('reviews', queryset=Review.objects.filter(approved=True).select_related('user')),
            'variants'
        ),
        slug=slug,
        available=True
    )

    discount_percentage = product.get_discount_percentage() if product.discount_price else 0
    related_products = Product.objects.filter(
        category=product.category,
        available=True
    ).exclude(id=product.id).order_by('?')[:4]

    product.savings = product.price - (product.discount_price or product.price)

    affiliate_link = None
    if product.is_dropship and product.supplier_url:
        try:
            affiliate_link = generate_affiliate_link(product.supplier_url)
        except Exception:
            logger.warning(f"Could not generate affiliate link for {product.slug}")

    variants_data = list(product.variants.all().values('id', 'size', 'color', 'price', 'quantity'))
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
        'review_form': ReviewForm(),
        'discount_percentage': discount_percentage,
        'affiliate_link': affiliate_link,
        'variants_json': variants_json,
        'variant_colors': list(variants_by_color.keys()),
        'variant_sizes': list(variants_by_size.keys()),
    }
    return render(request, 'store/product/detail.html', context)


@require_POST
@ajax_login_required
def mark_review_helpful(request, review_id):
    review = get_object_or_404(Review, id=review_id, approved=True)

    if request.user in review.helpful_voters.all():
        review.helpful_voters.remove(request.user)
        review.helpful_count = F('helpful_count') - 1
        review.save(update_fields=['helpful_count'])
        review.refresh_from_db()
        return JsonResponse({'success': True, 'unvoted': True, 'new_count': review.helpful_count})
    else:
        review.helpful_voters.add(request.user)
        review.helpful_count = F('helpful_count') + 1
        review.save(update_fields=['helpful_count'])
        review.refresh_from_db()
        return JsonResponse({'success': True, 'voted': True, 'new_count': review.helpful_count})


@require_POST
@ajax_login_required
def delete_review(request, review_id):
    review = get_object_or_404(Review, id=review_id, user=request.user)
    review.delete()
    messages.success(request, 'Your review was deleted successfully.')
    return JsonResponse({'success': True})

@require_POST
def stock_notification(request):
    try:
        data = json.loads(request.body)
        product_id = data.get('product_id')
        email = data.get('email', '').strip()

        if not product_id or not email:
            return JsonResponse({'success': False, 'message': 'Missing data.'}, status=400)

        validate_email(email)
        product = get_object_or_404(Product, id=product_id)
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
    """Generate both plaintext and HTML email content for confirmation."""
    confirmation_link = request.build_absolute_uri(
        reverse('store:confirm_subscription', args=[subscription.confirmation_token]))
    unsubscribe_link = request.build_absolute_uri(
        reverse('store:unsubscribe', args=[subscription.unsubscribe_token]))
    privacy_policy_link = request.build_absolute_uri(reverse('store:privacy'))

    plaintext_message = f"""Welcome to ASAI Newsletter!

Please confirm your subscription by clicking the link below:
{confirmation_link}

If you didn't request this subscription, you can safely ignore this email or unsubscribe here:
{unsubscribe_link}

Your subscription details:
- Email: {subscription.email}
- IP Address: {subscription.ip_address}
- Signup Date: {subscription.created_at.strftime('%Y-%m-%d %H:%M:%S')}

Privacy Policy: {privacy_policy_link}

Best regards,
ASAI Team
"""

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
            }}
            .container {{
                background: #ffffff;
                border-radius: 10px;
                padding: 30px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }}
            .header {{
                text-align: center;
                margin-bottom: 30px;
            }}
            .logo {{
                font-size: 32px;
                font-weight: bold;
                background: linear-gradient(45deg, #60a5fa, #a78bfa, #f472b6);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                margin-bottom: 10px;
            }}
            .button {{
                display: inline-block;
                padding: 14px 30px;
                background: linear-gradient(135deg, #2563eb, #4338ca);
                color: white !important;
                text-decoration: none;
                border-radius: 8px;
                font-weight: 600;
                margin: 20px 0;
                transition: transform 0.2s;
            }}
            .button:hover {{
                transform: translateY(-2px);
            }}
            .info-box {{
                background: #f8fafc;
                border-left: 4px solid #2563eb;
                padding: 15px;
                margin: 20px 0;
                border-radius: 4px;
            }}
            .footer {{
                margin-top: 30px;
                padding-top: 20px;
                border-top: 1px solid #e2e8f0;
                font-size: 12px;
                color: #64748b;
                text-align: center;
            }}
            .footer a {{
                color: #2563eb;
                text-decoration: none;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div class="logo">ASAI</div>
                <h2 style="color: #1e293b; margin: 0;">Welcome to Our Newsletter! 🎮</h2>
            </div>

            <p>Hi there!</p>

            <p>Thanks for subscribing to the ASAI newsletter. You're one click away from getting exclusive deals, 
            new product launches, and gaming tips delivered straight to your inbox.</p>

            <div style="text-align: center;">
                <a href="{confirmation_link}" class="button">Confirm My Subscription</a>
            </div>

            <p style="text-align: center; color: #64748b; font-size: 14px;">
                Or copy this link to your browser:<br>
                <code style="background: #f1f5f9; padding: 5px 10px; border-radius: 4px; display: inline-block; margin-top: 5px;">
                    {confirmation_link}
                </code>
            </p>

            <div class="info-box">
                <strong>Subscription Details:</strong><br>
                📧 Email: {subscription.email}<br>
                📍 IP Address: {subscription.ip_address}<br>
                📅 Date: {subscription.created_at.strftime('%B %d, %Y at %H:%M')}
            </div>

            <p style="color: #64748b; font-size: 14px;">
                <strong>Didn't request this?</strong><br>
                If you didn't sign up for our newsletter, you can safely ignore this email or 
                <a href="{unsubscribe_link}" style="color: #2563eb;">unsubscribe here</a>.
            </p>

            <div class="footer">
                <p>
                    <a href="{privacy_policy_link}">Privacy Policy</a> | 
                    <a href="{unsubscribe_link}">Unsubscribe</a>
                </p>
                <p>© 2025 ASAI. All rights reserved.<br>Made with ❤️ in Nairobi</p>
            </div>
        </div>
    </body>
    </html>
    """
    return plaintext_message, html_content


@require_POST
def subscribe(request):
    """Handle newsletter subscription with proper validation and error handling."""
    # Get email from POST data
    email = request.POST.get('email', '').strip()

    # Check if it's an AJAX request
    is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest'

    if not email:
        message = "Please enter an email address."
        if is_ajax:
            return JsonResponse({'success': False, 'message': message})
        messages.error(request, message)
        return redirect(request.META.get('HTTP_REFERER', 'store:product_list'))

    try:
        # Validate email format
        validate_email(email)

        # Check for existing subscription
        existing = NewsletterSubscription.objects.filter(email=email).first()

        if existing:
            if existing.confirmed and not existing.unsubscribed:
                message = "This email is already subscribed to our newsletter!"
                if is_ajax:
                    return JsonResponse({'success': False, 'message': message})
                messages.info(request, message)
                return redirect(request.META.get('HTTP_REFERER', 'store:product_list'))

            elif existing.unsubscribed:
                # Reactivate unsubscribed user
                existing.unsubscribed = False
                existing.confirmed = False
                existing.generate_tokens()
                existing.confirmation_sent = timezone.now()
                existing.save()

                # Send new confirmation email
                plaintext, html = create_confirmation_email_content(request, existing)
                send_email_async(
                    "Confirm Your ASAI Newsletter Subscription",
                    plaintext,
                    email,
                    html_message=html
                )

                message = "Welcome back! Please check your email to confirm your subscription."
                if is_ajax:
                    return JsonResponse({'success': True, 'message': message})
                messages.success(request, message)
                return redirect(request.META.get('HTTP_REFERER', 'store:product_list'))

            else:
                # Resend confirmation to pending subscription
                plaintext, html = create_confirmation_email_content(request, existing)
                send_email_async(
                    "Confirm Your ASAI Newsletter Subscription",
                    plaintext,
                    email,
                    html_message=html
                )

                message = "Confirmation email resent! Please check your inbox."
                if is_ajax:
                    return JsonResponse({'success': True, 'message': message})
                messages.warning(request, message)
                return redirect(request.META.get('HTTP_REFERER', 'store:product_list'))

        # Create new subscription
        subscription = NewsletterSubscription(
            email=email,
            ip_address=request.META.get('REMOTE_ADDR', ''),
            source_url=request.META.get('HTTP_REFERER', '')
        )
        subscription.generate_tokens()
        subscription.confirmation_sent = timezone.now()
        subscription.save()

        # Send confirmation email
        plaintext, html = create_confirmation_email_content(request, subscription)

        send_email_async(
            "Confirm Your ASAI Newsletter Subscription",
            plaintext,
            email,
            html_message=html
        )

        logger.info(f"Newsletter subscription initiated for {email}")

        message = "Success! Please check your email to confirm your subscription."
        if is_ajax:
            return JsonResponse({'success': True, 'message': message})
        messages.success(request, message)
        return redirect(request.META.get('HTTP_REFERER', 'store:product_list'))

    except ValidationError:
        logger.warning(f"Invalid email attempt: {email}")
        message = "Please enter a valid email address."
        if is_ajax:
            return JsonResponse({'success': False, 'message': message})
        messages.error(request, message)
        return redirect(request.META.get('HTTP_REFERER', 'store:product_list'))

    except Exception as e:
        logger.error(f"Subscription error for {email}: {str(e)}", exc_info=True)
        message = "An error occurred. Please try again later."
        if is_ajax:
            return JsonResponse({'success': False, 'message': message})
        messages.error(request, message)
        return redirect(request.META.get('HTTP_REFERER', 'store:product_list'))


def confirm_subscription(request, token):
    """Confirm newsletter subscription."""
    try:
        subscription = NewsletterSubscription.objects.get(
            confirmation_token=token,
            confirmed=False,
            unsubscribed=False
        )

        # Check if confirmation link has expired (24 hours)
        if (timezone.now() - subscription.confirmation_sent).days > 1:
            subscription.delete()
            logger.info(f"Expired subscription confirmation: {token}")
            messages.error(request, "This confirmation link has expired. Please subscribe again.")
            return redirect('store:product_list')

        # Confirm subscription
        subscription.confirmed = True
        subscription.confirmed_at = timezone.now()
        subscription.save()

        logger.info(f"Subscription confirmed: {subscription.email}")
        messages.success(request, "Thank you! Your subscription is now confirmed. Welcome to ASAI!")

    except NewsletterSubscription.DoesNotExist:
        logger.warning(f"Invalid confirmation token: {token}")
        messages.error(request, "Invalid or expired confirmation link.")

    return redirect('store:product_list')


def unsubscribe(request, token):
    """Handle newsletter unsubscription."""
    subscription = None

    try:
        subscription = NewsletterSubscription.objects.get(
            unsubscribe_token=token,
            unsubscribed=False
        )

        subscription.unsubscribed = True
        subscription.save()

        logger.info(f"Unsubscribed: {subscription.email}")
        messages.success(request, "You've been successfully unsubscribed from our newsletter.")

    except NewsletterSubscription.DoesNotExist:
        logger.warning(f"Invalid unsubscribe token: {token}")
        messages.error(request, "Invalid unsubscribe link.")

    return render(request, 'store/newsletter/unsubscribe.html', {
        'success': subscription is not None,
        'email': subscription.email if subscription else None
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
@user_passes_test(lambda u: u.is_staff, login_url='/accounts/login/')
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
    data = json.loads(request.body or '{}')
    query = data.get('query', '')[:255]
    results_count = data.get('results_count', 0)
    if query:
        try:
            SearchLog.objects.create(query=query, results_count=results_count,
                                     ip_address=request.META.get('REMOTE_ADDR'))
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
    return render(request, 'store/dashboard/import_products.html',
                  {'form': form, 'title': 'Import AliExpress Products'})