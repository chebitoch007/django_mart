from django.shortcuts import render, get_object_or_404, redirect
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Avg, Count, Q
from django.contrib import messages
from .models import Category, Product, ProductImage, Review
from cart.forms import CartAddProductForm
from .forms import ReviewForm


def product_list(request, category_slug=None):
    """
    Display a list of products, optionally filtered by category.
    Supports sorting and pagination.
    """
    category = None
    categories = Category.objects.filter(is_active=True).annotate(
        product_count=Count('products', filter=Q(products__available=True))
    )

    # Base queryset with optimizations
    products = Product.objects.filter(available=True).select_related('category')

    # Category filter
    if category_slug:
        category = get_object_or_404(Category, slug=category_slug)
        products = products.filter(category=category)

    # Sorting
    sort_by = request.GET.get('sort', '-created')
    sort_options = {
        'price_asc': 'price',
        'price_desc': '-price',
        'name': 'name',
        'rating': '-avg_rating',
        'popular': '-review_count',
        '-created': '-created'
    }

    # Annotate ratings and review counts if needed
    if sort_by in ['rating', 'popular']:
        products = products.annotate(
            avg_rating=Avg('reviews__rating'),
            review_count=Count('reviews')
        )

    products = products.order_by(sort_options.get(sort_by, '-created'))

    # Pagination
    paginator = Paginator(products, 12)
    page_number = request.GET.get('page')

    try:
        products = paginator.page(page_number)
    except PageNotAnInteger:
        products = paginator.page(1)
    except EmptyPage:
        products = paginator.page(paginator.num_pages)

    context = {
        'category': category,
        'categories': categories,
        'products': products,
        'sort_by': sort_by,
    }
    return render(request, 'store/product/list.html', context)


def product_detail(request, slug):
    """
    Display product details with related products, reviews, and cart functionality.
    """
    product = get_object_or_404(
        Product.objects
        .select_related('category')
        .prefetch_related('additional_images', 'reviews__user'),
        slug=slug,
        available=True
    )

    # Get related products (from same category, excluding current product)
    related_products = Product.objects.filter(
        category=product.category,
        available=True
    ).exclude(id=product.id)[:4]

    # Handle review submission
    review_form = ReviewForm()
    if request.method == 'POST' and request.user.is_authenticated:
        review_form = ReviewForm(request.POST)
        if review_form.is_valid():
            existing_review = Review.objects.filter(
                product=product,
                user=request.user
            ).first()

            if existing_review:
                messages.warning(request, 'You have already reviewed this product!')
            else:
                review = review_form.save(commit=False)
                review.product = product
                review.user = request.user
                review.save()
                product.update_rating()  # Update the cached rating
                messages.success(request, 'Thank you for your review!')
                return redirect('store:product_detail', slug=product.slug)

    # Cart product form
    cart_product_form = CartAddProductForm()

    context = {
        'product': product,
        'related_products': related_products,
        'cart_product_form': cart_product_form,
        'review_form': review_form,
    }
    return render(request, 'store/product/detail.html', context)


def legacy_product_redirect(request, id, slug):
    """
    Redirect old product URLs to new slug-only URLs.
    """
    product = get_object_or_404(Product, id=id)
    return redirect('store:product_detail', slug=product.slug, permanent=True)


def product_search(request):
    """
    Handle product search queries.
    """
    query = request.GET.get('q', '').strip()
    products = Product.objects.none()

    if query:
        products = Product.objects.filter(
            Q(name__icontains=query) |
            Q(description__icontains=query) |
            Q(category__name__icontains=query),
            available=True
        ).select_related('category').distinct()

    # Pagination
    paginator = Paginator(products, 12)
    page_number = request.GET.get('page')

    try:
        products = paginator.page(page_number)
    except PageNotAnInteger:
        products = paginator.page(1)
    except EmptyPage:
        products = paginator.page(paginator.num_pages)

    return render(request, 'store/product/search.html', {
        'products': products,
        'query': query
    })


def submit_review(request, slug):
    """
    Handle review submissions via AJAX or form post.
    """
    if not request.user.is_authenticated:
        messages.error(request, 'Please log in to submit a review.')
        return redirect('login')

    product = get_object_or_404(Product, slug=slug)

    if request.method == 'POST':
        form = ReviewForm(request.POST)
        if form.is_valid():
            # Check for existing review
            if Review.objects.filter(product=product, user=request.user).exists():
                messages.warning(request, 'You have already reviewed this product!')
            else:
                review = form.save(commit=False)
                review.product = product
                review.user = request.user
                review.save()
                product.update_rating()
                messages.success(request, 'Thank you for your review!')

    return redirect('store:product_detail', slug=product.slug)