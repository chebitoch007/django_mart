from django.shortcuts import render, get_object_or_404, redirect
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Avg, Q, Count, F, ExpressionWrapper, DecimalField
from django.views.generic import TemplateView
from .models import Category, Product, Review, NewsletterSubscription, ProductImage
from cart.forms import CartAddProductForm
from .forms import ReviewForm
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.utils import timezone
from .utils import send_email_async
import logging
from django.http import HttpRequest, request
from django.urls import reverse
from django.db.models.functions import Coalesce
from store.constants import CATEGORIES
from django.contrib.auth.decorators import login_required, user_passes_test
from .forms import ProductForm




# Constants for sorting options
SORT_OPTIONS = {
    'price_asc': 'price',
    'price_desc': '-price',
    'name': 'name',
    'rating': '-avg_rating',
    'popular': '-review_count',
    'newest': '-created',
    'discount': '-discount_percentage',
}


def get_sorted_products(products, sort_key):
    """Enhanced sorting with annotations for discount percentage"""
    # Annotate with calculated fields needed for sorting
    products = products.annotate(
        avg_rating=Coalesce(Avg('reviews__rating'), 0.0),
        review_count=Count('reviews'),
        # FIXED: Corrected typo in discount_price field name
        discount_percentage=ExpressionWrapper(
            (F('price') - F('discount_price')) / F('price') * 100,
            output_field=DecimalField()
        ) if 'discount' in sort_key else None
    )

    sort_field = SORT_OPTIONS.get(sort_key, '-created')
    return products.order_by(sort_field)


def product_list(request, category_slug=None):
    """Enhanced product listing with filtering, sorting, and pagination"""
    category = None
    categories = Category.objects.filter(is_active=True).annotate(
        _product_count_cache=Count('products', filter=Q(products__available=True))
    )

    products = Product.objects.filter(available=True).select_related('category')

    if category_slug:
        category = get_object_or_404(Category, slug=category_slug)
        products = products.filter(category=category)

    # Apply price filter
    max_price = request.GET.get('max_price')
    if max_price and max_price.isdigit():
        products = products.filter(price__lte=max_price)

    # Apply stock filter
    in_stock = request.GET.get('in_stock')
    if in_stock == 'true':
        products = products.filter(stock__gt=0)

    # Validate and apply sorting
    sort_by = request.GET.get('sort', '-created')
    products = get_sorted_products(products, sort_by)

    # Pagination
    paginator = Paginator(products, 12)
    page_number = request.GET.get('page')

    try:
        products_page = paginator.page(page_number)
    except (PageNotAnInteger, EmptyPage):
        products_page = paginator.page(1)

    context = {
        'category': category,
        'categories': categories,
        'products': products_page,
        'sort_by': sort_by,
        'sort_options': SORT_OPTIONS,
        'max_price': max_price or 1000,
        'in_stock': in_stock == 'true',
    }
    return render(request, 'store/product/list.html', context)


def product_detail(request, slug):
    """Optimized product detail view with prefetch_related"""
    product = get_object_or_404(
        Product.objects
        .select_related('category')
        .prefetch_related('additional_images', 'reviews__user'),
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
    }
    return render(request, 'store/product/detail.html', context)


def home(request):
    """Enhanced home page with featured products and categories"""
    featured_products = Product.objects.filter(
        available=True,
        featured=True
    ).select_related('category').prefetch_related('additional_images')[:8]

    categories = Category.objects.filter(is_active=True).annotate(
        _product_count_cache=Count('products', distinct=True)
    ).order_by('name')[:5]

    # Add placeholder for categories without images
    for category in categories:
        if not category.image:
            category.image_placeholder = True

    return render(request, 'store/home.html', {
        'featured_products': featured_products,
        'categories': categories
    })


def legacy_product_redirect(request, id, slug):
    """Redirect old product URLs to new slug-only URLs"""
    product = get_object_or_404(Product, id=id)
    return redirect('store:product_detail', slug=product.slug, permanent=True)


def product_search(request):
    """Handle product search queries"""
    query = request.GET.get('q', '').strip()
    products = Product.objects.none()

    if not query:
        messages.info(request, "Please enter a search term")
        return redirect('store:product_list')

    products = Product.objects.filter(available=True).select_related('category').annotate(
        avg_rating=Avg('reviews__rating'),
        review_count=Count('reviews')
    )

    paginator = Paginator(products, 16)
    page_number = request.GET.get('page')

    try:
        products = paginator.page(page_number)
    except PageNotAnInteger:
        products = paginator.page(1)
    except EmptyPage:
        products = paginator.page(paginator.num_pages)

    return render(request, 'store/product/search.html', {
        'products': products,
        'query': query,
        'sort_options': SORT_OPTIONS
    })


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
    return user.is_staff


@login_required
@user_passes_test(is_staff)
def add_product(request):
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            product = form.save()
            # Images are handled in form.save()
            messages.success(request, f'Product "{product.name}" added successfully!')
            return redirect('store:product_detail', slug=product.slug)
    else:
        form = ProductForm()
    return render(request, 'store/dashboard/add_product.html', {'form': form})

@login_required
@user_passes_test(is_staff)
def product_dashboard(request):
    products = Product.objects.select_related('category').order_by('-created')
    return render(request, 'store/dashboard/product_dashboard.html', {'products': products})


@login_required
@user_passes_test(is_staff)
def edit_product(request, slug):
    product = get_object_or_404(Product, slug=slug)
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES, instance=product)
        if form.is_valid():
            product = form.save()

            # Handle image deletion
            if 'delete_images' in request.POST:
                image_ids = request.POST.getlist('delete_images')
                ProductImage.objects.filter(id__in=image_ids, product=product).delete()

            messages.success(request, f'Product "{product.name}" updated successfully!')
            return redirect('store:product_detail', slug=product.slug)
    else:
        form = ProductForm(instance=product)

    return render(request, 'store/dashboard/add_product.html', {
        'form': form,
        'product': product
    })

@login_required
@user_passes_test(is_staff)
def delete_product(request, slug):
    product = get_object_or_404(Product, slug=slug)
    if request.method == 'POST':
        product_name = product.name
        product.delete()
        messages.success(request, f'Product "{product_name}" deleted successfully!')
        return redirect('store:product_dashboard')

    return render(request, 'store/dashboard/delete_product.html', {'product': product})
