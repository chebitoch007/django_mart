#payment/urls.py


from django.urls import path
from . import views

app_name = 'payment'

urlpatterns = [
    # M-Pesa URLs
    path('webhook/mpesa/', views.payment_webhook, {'provider': 'MPESA'}, name='mpesa_webhook'),
    path('mpesa-status/', views.mpesa_status, name='mpesa_status'),
    path('mpesa/callback/', views.mpesa_callback, name='mpesa_callback'),
    path('retry-mpesa/<int:payment_id>/', views.retry_mpesa_payment, name='retry_mpesa_payment'),

    # PayPal URLs - FIXED names
    path('paypal/create/', views.create_paypal_payment, name='paypal_create'),
    path('paypal/execute/<int:order_id>/', views.execute_paypal_payment, name='paypal_execute'),
    path('paypal/status/', views.paypal_status, name='paypal_status'),
    path('webhook/paypal/', views.payment_webhook, {'provider': 'PAYPAL'}, name='paypal_webhook'),

    # Other URLs
    path('initiate/', views.initiate_payment, name='initiate_payment'),
  #  path('mpesa/initiate/', views.initiate_mpesa_payment_view, name='initiate_mpesa_payment'),
    path('process/<int:order_id>/', views.process_payment, name='process_payment'),

    # ✅ ADD MISSING URL FOR PAYPAL CHECKOUT
    path('paypal/checkout/<int:order_id>/', views.paypal_checkout, name='paypal_checkout'),
    path('paypal/return/<int:order_id>/', views.paypal_payment_return, name='paypal_return'),
    path('paypal/cancel/<int:order_id>/', views.paypal_payment_cancel, name='paypal_cancel'),
]


