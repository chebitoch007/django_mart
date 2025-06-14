from django.urls import path
from .views import (
    PaymentPendingView,
    CashPaymentCompleteView,
    MobileMoneyVerifyView,
    PaymentCompleteView, mobile_money_verification
)

app_name = 'payment'

urlpatterns = [

    path('pending/<int:pk>/', PaymentPendingView.as_view(), name='payment-pending'),
    path('cash/<int:pk>/', CashPaymentCompleteView.as_view(), name='cash-payment'),
    path('verify/<int:pk>/', MobileMoneyVerifyView.as_view(), name='verify-mobile'),
    path('complete/<int:pk>/', PaymentCompleteView.as_view(), name='payment-complete'),
    path('mobile/<int:payment_id>/', mobile_money_verification, name='mobile-verify'),
]