#payment/urls.py


from django.urls import path
from . import views

app_name = 'payment'

urlpatterns = [
    # M-Pesa URLs
    path('webhook/mpesa/', views.payment_webhook, {'provider': 'MPESA'}, name='mpesa_webhook'),
    path('mpesa-status/', views.mpesa_status, name='mpesa_status'),
    path('retry-mpesa/<int:payment_id>/', views.retry_mpesa_payment, name='retry_mpesa_payment'),

    # PayPal URLs
    path('paypal/create/', views.create_paypal_payment, name='paypal_create'),
    path('paypal/execute/<int:order_id>/', views.execute_paypal_payment, name='paypal_execute'),
    path('paypal/status/', views.paypal_status, name='paypal_status'),
    path('webhook/paypal/', views.payment_webhook, {'provider': 'PAYPAL'}, name='paypal_webhook'),

    # Other URLs
    path('initiate/', views.initiate_payment, name='initiate_payment'),
    path('process/<int:order_id>/', views.process_payment, name='process_payment'),
    path('paypal/return/<int:order_id>/', views.paypal_payment_return, name='paypal_return'),
    path('paypal/cancel/<int:order_id>/', views.paypal_payment_cancel, name='paypal_cancel'),
]

