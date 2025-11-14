# ========== blog/urls.py ==========
from django.urls import path
from . import views

app_name = 'blog'

urlpatterns = [
    # Blog List
    path('', views.blog_list, name='blog_list'),

    # Post Detail
    path('post/<slug:slug>/', views.post_detail, name='post_detail'),

    # Category & Tags
    path('category/<slug:slug>/', views.category_posts, name='category'),
    path('tag/<slug:slug>/', views.tag_posts, name='tag'),

    # Comments
    path('post/<slug:slug>/comment/', views.add_comment, name='add_comment'),

    # Subscribe
    path('subscribe/', views.subscribe, name='subscribe'),
    path('unsubscribe/<str:email>/', views.unsubscribe, name='unsubscribe'),

    # Search
    path('search/', views.blog_search, name='search'),
]