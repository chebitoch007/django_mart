from django.conf import settings
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.urls import reverse_lazy
from .forms import UserRegisterForm, ProfileUpdateForm, NotificationPreferencesForm
from .models import Profile
from orders.models import Order
from django.contrib.auth import login as auth_login
from django.contrib.auth.views import PasswordChangeView, LoginView
from django.views.generic import FormView, TemplateView
from django.utils.decorators import method_decorator

from .forms import (
    UserProfileForm,
    AddressForm,
    PaymentMethodForm,
    PasswordChangeForm
)
from .models import Address, PaymentMethod



class CustomLoginView(LoginView):
    template_name = 'users/login.html'
    redirect_authenticated_user = True

    def form_valid(self, form):
        remember_me = self.request.POST.get('remember_me', False)
        if not remember_me:
            self.request.session.set_expiry(0)
            self.request.session.modified = True
        return super().form_valid(form)

def register(request):
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            user = form.save()

            # Handle remember me functionality
            auth_login(request, user)

            # Store consent information
            user.terms_accepted = True
            user.privacy_accepted = True
            user.consent_version = settings.PASSWORD_POLICY['version']
            user.save()

            messages.success(request, 'Registration successful! You are now logged in.')
            return redirect('store:home')
    else:
        form = UserRegisterForm()

    password_policy = getattr(settings, 'PASSWORD_POLICY', {
        'requirements': [
            'At least 8 characters',
            'Mix of uppercase and lowercase letters',
            'At least one number',
            'At least one special character'
        ],
        'version': '1.0'
    })

    return render(request, 'users/register.html', {
        'form': form,
        'password_policy': password_policy
    })

@method_decorator(login_required, name='dispatch')
class ProfileUpdateView(FormView):
    template_name = 'users/profile_update.html'
    form_class = ProfileUpdateForm
    success_url = reverse_lazy('users:profile')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['instance'] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.save()
        messages.success(self.request, 'Profile updated successfully')
        return super().form_valid(form)


@method_decorator(login_required, name='dispatch')
class NotificationPreferencesView(FormView):
    template_name = 'users/notification_preferences.html'
    form_class = NotificationPreferencesForm
    success_url = reverse_lazy('users:profile')

    def get_initial(self):
        initial = super().get_initial()
        profile = self.request.user.profile
        initial['email_notifications'] = profile.email_notifications
        initial['sms_notifications'] = profile.sms_notifications
        return initial

    def form_valid(self, form):
        profile = self.request.user.profile
        profile.email_notifications = form.cleaned_data['email_notifications']
        profile.sms_notifications = form.cleaned_data['sms_notifications']
        profile.save()
        messages.success(self.request, 'Notification preferences updated')
        return super().form_valid(form)


@login_required
def profile(request):
    orders = Order.objects.filter(user=request.user).order_by('-created')[:5]
    profile, created = Profile.objects.get_or_create(user=request.user)

    return render(request, 'users/profile.html', {
        'profile': profile,
        'recent_orders': orders
    })


class CustomPasswordChangeView(PasswordChangeView):
    template_name = 'users/password_change.html'
    success_url = reverse_lazy('users:password_change_done')

    def form_valid(self, form):
        messages.success(self.request, 'Password changed successfully')
        return super().form_valid(form)


@login_required
def profile_update(request):
    if request.method == 'POST':
        form = ProfileUpdateForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully')
            return redirect('users:profile')
    else:
        form = ProfileUpdateForm(instance=request.user)

    return render(request, 'users/profile_update.html', {'form': form})


def notification_preferences(request):
    return None

class TermsView(TemplateView):
    template_name = "users/legal/terms.html"
    extra_context = {"effective_date": "2025-01-01"}  # Update dates dynamically

class PrivacyView(TemplateView):
    template_name = "users/legal/privacy.html"
    extra_context = {"data_officer": "contact@djangomart.co.ke"}

class ReturnPolicyView(TemplateView):
    template_name = 'users/legal/return-policy.html'



class AccountView(TemplateView):
    template_name = "users/account.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        # Initialize forms
        context['profile_form'] = UserProfileForm(instance=user)
        context['address_form'] = AddressForm()
        context['payment_form'] = PaymentMethodForm()
        context['password_form'] = PasswordChangeForm(user)

        # Get user data
        context['addresses'] = Address.objects.filter(user=user)
        context['payment_methods'] = PaymentMethod.objects.filter(user=user)
        context['recent_orders'] = user.orders.all().order_by('-created_at')[:5]

        return context

    def post(self, request, *args, **kwargs):
        user = request.user
        form_type = request.POST.get('form_type')

        if form_type == 'profile':
            form = UserProfileForm(request.POST, instance=user)
            if form.is_valid():
                form.save()
                messages.success(request, 'Profile updated successfully')
            else:
                messages.error(request, 'Error updating profile')

        elif form_type == 'address':
            form = AddressForm(request.POST)
            if form.is_valid():
                address = form.save(commit=False)
                address.user = user
                address.save()
                messages.success(request, 'Address added successfully')

        elif form_type == 'payment':
            form = PaymentMethodForm(request.POST)
            if form.is_valid():
                payment = form.save(commit=False)
                payment.user = user
                payment.save()
                messages.success(request, 'Payment method added')

        elif form_type == 'password':
            form = PasswordChangeForm(user, request.POST)
            if form.is_valid():
                form.save()
                messages.success(request, 'Password updated successfully')

        return redirect('users:account')


account_view = login_required(AccountView.as_view())



