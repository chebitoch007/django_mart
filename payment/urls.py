# payment/urls.py
from django.urls import path
from . import views, paystack_views

app_name = 'payment'

urlpatterns = [
    # --- Core Payment Endpoints ---
    path('initiate/', views.initiate_payment, name='initiate_payment'),
    path('process/<int:order_id>/', views.process_payment, name='process_payment'),

    # --- PayPal ---
    path('paypal/create/', views.create_paypal_payment, name='create_paypal_payment'),
    path('paypal/status/', views.paypal_status, name='paypal_status'),
    path('paypal/return/<int:order_id>/', views.paypal_payment_return, name='paypal_payment_return'),
    path('paypal/cancel/<int:order_id>/', views.paypal_payment_cancel, name='paypal_payment_cancel'),

    # --- M-Pesa ---
    path('mpesa/status/', views.mpesa_status, name='mpesa_status'),
    path('mpesa/retry/<int:payment_id>/', views.retry_mpesa_payment, name='retry_mpesa_payment'),
    path('mpesa/test/', views.test_mpesa_connection, name='test_mpesa_connection'),

    # --- Webhooks ---
    path('webhook/<str:provider>/', views.payment_webhook, name='payment_webhook'),

    # --- Debugging / Internal Tools ---
    path('debug/<str:checkout_request_id>/', views.debug_payment, name='debug_payment'),

    # --- Paystack ---
    path('paystack/initialize/', paystack_views.initialize_paystack_payment, name='initialize_paystack'),
    path('paystack/callback/', paystack_views.paystack_callback, name='paystack_callback'),
    path('paystack/webhook/', paystack_views.paystack_webhook, name='paystack_webhook'),
    path('paystack/status/', paystack_views.paystack_status, name='paystack_status'),
]
