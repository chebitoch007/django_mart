from django.urls import path
from . import views

app_name = 'payment'

urlpatterns = [
    path('<int:order_id>/', views.PaymentView.as_view(), name='process'),
    path('stripe-webhook/', views.stripe_webhook, name='stripe_webhook'),

    # PayPal
    path('paypal/create/<int:order_id>/', views.create_paypal_order, name='create_paypal_order'),
    path('paypal/capture/<int:order_id>/', views.capture_paypal_order, name='capture_paypal_order'),

    # M-Pesa
    path('mpesa/initiate/<int:order_id>/', views.initiate_mpesa_payment, name='initiate_mpesa'),
    path('mpesa/callback/', views.mpesa_callback, name='mpesa_callback'),
]