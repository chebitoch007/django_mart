from django.contrib.auth.decorators import login_required
from django.urls import path
from . import views
from .views import OrderListView, OrderDetailView, OrderSuccessView

app_name = 'orders'

urlpatterns = [
    path('', OrderListView.as_view(), name='order_list'),
    path('<int:pk>/', OrderDetailView.as_view(), name='order_detail'),
    path('checkout/', login_required(views.checkout), name='checkout'),
    path('history/', views.order_history, name='history'),
    path('success/', OrderSuccessView.as_view(), name='success'),
]

