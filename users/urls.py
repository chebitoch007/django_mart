from django.urls import path, reverse_lazy
from django.contrib.auth import views as auth_views
from . import views
from .views import (
    CustomPasswordChangeView,
    TermsView,
    PrivacyView,
    ReturnPolicyView,
    register,
    profile,
    profile_update,
    notification_preferences
)

app_name = 'users'

urlpatterns = [
    path('account/', views.account_view, name='account'),
    # Authentication
    path('login/',
        auth_views.LoginView.as_view(
            template_name='users/login.html',
            redirect_authenticated_user=True
        ), name='login'),
    path('logout/',
        auth_views.LogoutView.as_view(
            template_name='users/logout.html'
        ), name='logout'),
    path('register/', register, name='register'),

    # Profile
    path('profile/', profile, name='profile'),
    path('profile/update/', profile_update, name='profile_update'),
    path('profile/notifications/',
        notification_preferences,
        name='notification_prefs'),

    # Password management
    path('password/change/',
        CustomPasswordChangeView.as_view(
            template_name='users/password_change.html'
        ), name='password_change'),
    path('password/change/done/',
        auth_views.PasswordChangeDoneView.as_view(
            template_name='users/password_change_done.html'
        ), name='password_change_done'),
    path('password/reset/',
        auth_views.PasswordResetView.as_view(
            template_name='users/password_reset.html',
            email_template_name='users/password_reset_email.html',
            subject_template_name='users/password_reset_subject.txt'
        ), name='password_reset'),
    path('password/reset/done/',
        auth_views.PasswordResetDoneView.as_view(
            template_name='users/password_reset_done.html'
        ), name='password_reset_done'),
    path('password/reset/confirm/<uidb64>/<token>/',
     auth_views.PasswordResetConfirmView.as_view(
         template_name='users/password_reset_confirm.html',
         success_url = reverse_lazy('users:password_reset_complete')
     ),
     name='password_reset_confirm'),
    path('password/reset/complete/',
        auth_views.PasswordResetCompleteView.as_view(
            template_name='users/password_reset_complete.html'
        ), name='password_reset_complete'),

    # Legal pages
    path('legal/terms/', TermsView.as_view(), name='terms'),
    path('legal/privacy/', PrivacyView.as_view(), name='privacy'),
    path('legal/return-policy/', ReturnPolicyView.as_view(), name='return_policy'),
]