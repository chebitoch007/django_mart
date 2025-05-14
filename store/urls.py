from django.urls import path
from . import views

app_name = 'store'

urlpatterns = [
    # Product listings
    path('', views.product_list, name='product_list'),
    path('category/<slug:category_slug>/', views.product_list, name='product_list_by_category'),

    # Product detail (new SEO-friendly version)
    path('product/<slug:slug>/', views.product_detail, name='product_detail'),

    # Review submission
    path('product/<slug:slug>/review/', views.submit_review, name='submit_review'),

    # Search
    path('search/', views.product_search, name='product_search'),

    # Legacy URL pattern (keep for existing links/bookmarks)
    path('<int:id>/<slug:slug>/', views.legacy_product_redirect, name='legacy_product_detail'),
]