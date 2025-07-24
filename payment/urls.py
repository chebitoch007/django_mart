from django.urls import path

from . import views
from .views import (
    PaymentPendingView,
    CashPaymentCompleteView,
    MobileMoneyVerifyView,
    PaymentCompleteView,
    mobile_money_verification,
    ProcessPaymentView,
    PayPalPaymentView,

    PaymentMethodCreateView,
    PaymentMethodUpdateView,
    PaymentMethodDeleteView,
    set_default_payment,
    payment_methods,
    PaymentExpiredView,
)

app_name = 'payment'

urlpatterns = [
    path('methods/', payment_methods, name='payment_methods'),
    path('methods/<int:pk>/set-default/', set_default_payment, name='set_default_payment'),
    path('methods/create/', PaymentMethodCreateView.as_view(), name='payment_method_create'),
    path('methods/<int:pk>/update/', PaymentMethodUpdateView.as_view(), name='payment_method_update'),
    path('methods/<int:pk>/delete/', PaymentMethodDeleteView.as_view(), name='payment_method_delete'),

    path('pending/<int:pk>/', PaymentPendingView.as_view(), name='payment-pending'),
    path('cash/<int:pk>/', CashPaymentCompleteView.as_view(), name='cash-payment'),
    path('verify/<int:pk>/', MobileMoneyVerifyView.as_view(), name='verify-mobile'),
    path('complete/<int:pk>/', PaymentCompleteView.as_view(), name='payment-complete'),
    path('mobile/<int:payment_id>/', mobile_money_verification, name='mobile-verify'),

    path('paypal/<int:order_id>/', PayPalPaymentView.as_view(), name='paypal-payment'),

    path('currency-convert/', views.currency_convert, name='currency_convert'),
    path('process-payment/', views.process_payment, name='process_payment'),

    path('expired/', PaymentExpiredView.as_view(), name='payment-expired'),
]