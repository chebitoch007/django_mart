# users/urls.py
from .views import session_keepalive, CustomPasswordResetView
from django.contrib.auth import views as auth_views
from . import views
from .views import (
    resend_password_reset_email,
    CustomPasswordChangeView,
    TermsView,
    PrivacyView,
    ReturnPolicyView,
    register,
    # REMOVED ProfileUpdateView
    AddressCreateView,
    AddressUpdateView,
    AddressDeleteView,
    set_default_address,
    AccountView,
    # REMOVED NotificationPreferencesView
    CustomLogoutView,
    LogoutSuccessView,
    AccountDeleteView,
    CustomLoginView,
)
from django.urls import path, reverse_lazy
from django.views.generic.base import RedirectView

app_name = 'users'

urlpatterns = [
    # Redirect /accounts/ to /accounts/account/ for clarity
    path('', RedirectView.as_view(url=reverse_lazy('users:account')), name='account_root'),

    path('account/', AccountView.as_view(), name='account'),

    # Authentication
    # path('login/',auth_views.LoginView.as_view(template_name='users/login.html',redirect_authenticated_user=True), name='login'),
    path('login/', CustomLoginView.as_view(), name='login'),

    path('logout/', CustomLogoutView.as_view(), name='logout'),
    path('logout-success/', LogoutSuccessView.as_view(), name='logout_success'),

    path('register/', register, name='register'),

    # Profile management - now handled through account page
    # UPDATED to use function-based view
    path('profile/update/', views.profile_update_view, name='profile_update'),

    # REMOVED notification_prefs URL
    # path('profile/notifications/',
    #      NotificationPreferencesView.as_view(),
    #      name='notification_prefs'),

    # Address management
    path('address/add/', AddressCreateView.as_view(), name='add_address'),
    path('address/<int:pk>/edit/', AddressUpdateView.as_view(), name='edit_address'),
    path('address/<int:pk>/delete/', AddressDeleteView.as_view(), name='delete_address'),
    path('address/<int:pk>/set-default/', set_default_address, name='set_default_address'),

    # Profile image update
    path('profile/image/', views.update_profile_image, name='update_profile_image'),

    # Password management
    path('password-change/', CustomPasswordChangeView.as_view(), name='password_change'),
    path('password-change/done/',
         auth_views.PasswordChangeDoneView.as_view(
             template_name='users/password_change_done.html'
         ),
         name='password_change_done'),

    path('password-reset/', CustomPasswordResetView.as_view(), name='password_reset'),

    path('password-reset/done/',
         auth_views.PasswordResetDoneView.as_view(
             template_name='users/password_reset_done.html'
         ),
         name='password_reset_done'),

    path('password-reset-confirm/<uidb64>/<token>/',
         auth_views.PasswordResetConfirmView.as_view(
             template_name='users/password_reset_confirm.html',
             success_url='/accounts/password-reset-complete/'  # Changed to /accounts/
         ),
         name='password_reset_confirm'),

    path('password-reset-complete/',
         auth_views.PasswordResetCompleteView.as_view(
             template_name='users/password_reset_complete.html'
         ),
         name='password_reset_complete'),

    path('password-reset/resend/',
         resend_password_reset_email,
         name='password_reset_resend'),

    # Legal pages
    path('legal/terms/', TermsView.as_view(), name='terms'),
    path('legal/privacy/', PrivacyView.as_view(), name='privacy'),
    path('legal/return-policy/', ReturnPolicyView.as_view(), name='return_policy'),
    path('account/delete/', AccountDeleteView.as_view(), name='account_delete'),
    path('session-keepalive/', session_keepalive, name='session_keepalive'),

]