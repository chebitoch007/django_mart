from django.urls import path
from . import views

from .views import add_product, product_dashboard, edit_product, delete_product

app_name = 'store'

urlpatterns = [
    # Home & Core Pages
    path('', views.home, name='home'),
    path('categories/', views.product_categories, name='categories'),
    path('search/', views.product_search, name='product_search'),

    # Product URLs
    path('products/', views.product_list, name='product_list'),
    path('products/category/<slug:category_slug>/', views.product_list, name='product_list_by_category'),
    path('products/<slug:slug>/', views.product_detail, name='product_detail'),
    path('products/<slug:slug>/review/', views.submit_review, name='submit_review'),

    # Legacy Support (Redirect old URLs)
    path('products/<int:id>/<slug:slug>/', views.legacy_product_redirect, name='legacy_product_detail'),
    path('subscribe/', views.subscribe, name='subscribe'),
    path('confirm-subscription/<str:token>/', views.confirm_subscription, name='confirm_subscription'),
    path('unsubscribe/<str:token>/', views.unsubscribe, name='unsubscribe'),
    path('test-template/<str:template>/', views.TemplateTestView.as_view(), name='template_test'),



    path('contact/', views.contact, name='contact'),
    path('faq/', views.faq, name='faq'),
    path('shipping/', views.shipping, name='shipping'),
    path('returns/', views.returns, name='returns'),
    path('warranty/', views.warranty, name='warranty'),
    path('track-order/', views.tracking, name='tracking'),



    path('privacy-policy/', views.privacy, name='privacy'),
    path('terms-of-service/', views.terms, name='terms'),
    path('cookie-policy/', views.cookies, name='cookies'),
    path('accessibility/', views.accessibility, name='accessibility'),
    path('sitemap/', views.sitemap, name='sitemap'),

    path('dashboard/products/', product_dashboard, name='product_dashboard'),
    path('dashboard/products/add/', add_product, name='add_product'),
    path('dashboard/products/edit/<slug:slug>/', edit_product, name='edit_product'),
    path('dashboard/products/delete/<slug:slug>/', delete_product, name='delete_product'),
]