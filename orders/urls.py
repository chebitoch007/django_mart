#orders/urls.py

from django.contrib.auth.decorators import login_required
from django.urls import path
from . import views
from .views import OrderDetailView, OrderSuccessView, CheckoutView, create_order, OrderListView
from orders import views as order_views


app_name = 'orders'

urlpatterns = [
    path('', OrderListView.as_view(), name='order_list'),

    path('<int:pk>/', views.OrderDetailView.as_view(), name='order_detail'),

    path('checkout/', login_required(CheckoutView.as_view()), name='checkout'),

    path('checkout/<int:order_id>/', login_required(CheckoutView.as_view()), name='checkout_order'),

    #path('', views.order_history, name='order_list'),
    path("success/<int:order_id>/", views.OrderSuccessView.as_view(), name="success"),
    path('shipping/', views.create_order, name='create_order'),
    path('update-payment-method/', order_views.update_payment_method, name='update_payment_method'),
]

