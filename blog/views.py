from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.utils import timezone
from .models import BlogPost, BlogCategory, BlogTag, BlogComment, BlogSubscriber


def blog_list(request):
    """List all published blog posts"""
    posts = BlogPost.objects.filter(
        status='published',
        published_at__lte=timezone.now()
    ).select_related('author', 'category').prefetch_related('tags')

    # Filters
    category = request.GET.get('category')
    tag = request.GET.get('tag')

    if category:
        posts = posts.filter(category__slug=category)
    if tag:
        posts = posts.filter(tags__slug=tag)

    # Featured posts for hero section
    featured_posts = posts.filter(is_featured=True)[:3]

    # Pagination
    paginator = Paginator(posts, 9)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Sidebar data
    categories = BlogCategory.objects.filter(is_active=True)
    popular_posts = posts.order_by('-views')[:5]
    recent_posts = posts.order_by('-published_at')[:5]
    all_tags = BlogTag.objects.all()[:20]

    context = {
        'posts': page_obj,
        'featured_posts': featured_posts,
        'categories': categories,
        'popular_posts': popular_posts,
        'recent_posts': recent_posts,
        'tags': all_tags,
    }
    return render(request, 'blog/blog_list.html', context)


def post_detail(request, slug):
    """Blog post detail page"""
    post = get_object_or_404(
        BlogPost,
        slug=slug,
        status='published',
        published_at__lte=timezone.now()
    )

    # Increment view count
    post.views += 1
    post.save(update_fields=['views'])

    # Get comments
    comments = post.comments.filter(
        is_approved=True,
        parent__isnull=True
    ).select_related('user').order_by('created_at')

    # Related posts
    related_posts = BlogPost.objects.filter(
        status='published',
        category=post.category
    ).exclude(id=post.id)[:3]

    # Sidebar data
    categories = BlogCategory.objects.filter(is_active=True)
    popular_posts = BlogPost.objects.filter(
        status='published'
    ).order_by('-views')[:5]

    context = {
        'post': post,
        'comments': comments,
        'related_posts': related_posts,
        'categories': categories,
        'popular_posts': popular_posts,
    }
    return render(request, 'blog/post_detail.html', context)


def category_posts(request, slug):
    """Posts filtered by category"""
    category = get_object_or_404(BlogCategory, slug=slug, is_active=True)
    posts = BlogPost.objects.filter(
        status='published',
        category=category,
        published_at__lte=timezone.now()
    )

    # Pagination
    paginator = Paginator(posts, 9)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'category': category,
        'posts': page_obj,
    }
    return render(request, 'blog/category_posts.html', context)


def tag_posts(request, slug):
    """Posts filtered by tag"""
    tag = get_object_or_404(BlogTag, slug=slug)
    posts = BlogPost.objects.filter(
        status='published',
        tags=tag,
        published_at__lte=timezone.now()
    )

    # Pagination
    paginator = Paginator(posts, 9)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'tag': tag,
        'posts': page_obj,
    }
    return render(request, 'blog/tag_posts.html', context)


@login_required
def add_comment(request, slug):
    """Add a comment to a blog post"""
    if request.method == 'POST':
        post = get_object_or_404(BlogPost, slug=slug, status='published')
        content = request.POST.get('content')
        parent_id = request.POST.get('parent_id')

        if content:
            comment = BlogComment.objects.create(
                post=post,
                user=request.user,
                content=content,
                parent_id=parent_id if parent_id else None
            )
            messages.success(request, 'Comment added successfully!')

        return redirect('blog:post_detail', slug=slug)

    return redirect('blog:blog_list')


def subscribe(request):
    """Subscribe to blog updates"""
    if request.method == 'POST':
        email = request.POST.get('email')

        if email:
            subscriber, created = BlogSubscriber.objects.get_or_create(email=email)

            if created:
                messages.success(request, 'Successfully subscribed to blog updates!')
            elif not subscriber.is_active:
                subscriber.is_active = True
                subscriber.save()
                messages.success(request, 'Welcome back! You\'re subscribed again.')
            else:
                messages.info(request, 'You\'re already subscribed!')

        return redirect(request.META.get('HTTP_REFERER', 'blog:blog_list'))

    return redirect('blog:blog_list')


def unsubscribe(request, email):
    """Unsubscribe from blog updates"""
    try:
        subscriber = BlogSubscriber.objects.get(email=email)
        subscriber.is_active = False
        subscriber.unsubscribed_at = timezone.now()
        subscriber.save()
        messages.success(request, 'You have been unsubscribed successfully.')
    except BlogSubscriber.DoesNotExist:
        messages.error(request, 'Email not found in our subscribers list.')

    return redirect('blog:blog_list')


def blog_search(request):
    """Search blog posts"""
    query = request.GET.get('q', '')

    if query:
        posts = BlogPost.objects.filter(
            Q(title__icontains=query) |
            Q(content__icontains=query) |
            Q(excerpt__icontains=query),
            status='published',
            published_at__lte=timezone.now()
        )
    else:
        posts = BlogPost.objects.none()

    # Pagination
    paginator = Paginator(posts, 9)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'posts': page_obj,
        'query': query,
    }
    return render(request, 'blog/search_results.html', context)