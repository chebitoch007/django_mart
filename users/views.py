# users/views.py
from decimal import Decimal

from django.conf import settings
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.urls import reverse_lazy

from payment.forms import PaymentMethodForm
from .forms import UserRegisterForm, ProfileUpdateForm, NotificationPreferencesForm
from .forms import AddressForm, PasswordChangeForm
from .models import Profile, Address
from payment.models import PaymentMethod
from orders.models import Order
from django.contrib.auth import login as auth_login
from django.contrib.auth.views import PasswordChangeView, LoginView
from django.views.generic import TemplateView, UpdateView, CreateView, DeleteView
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.db.models import Sum, Count, Avg, F, ExpressionWrapper, DecimalField

from payment.models import PaymentMethod



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
            user = form.save(commit=False)

            # Save registration address to user model
            user.registration_street_address = form.cleaned_data['street_address']
            user.registration_city = form.cleaned_data['city']
            user.registration_state = form.cleaned_data['state']
            user.registration_postal_code = form.cleaned_data['postal_code']

            user.save()

            # Create profile for user
            Profile.objects.create(user=user)

            auth_login(request, user)
            messages.success(request, 'Registration successful! You are now logged in.')
            return redirect('store:home')
    else:
        form = UserRegisterForm()

    return render(request, 'users/register.html', {
        'form': form,
        'password_policy': settings.PASSWORD_POLICY
    })


@method_decorator(login_required, name='dispatch')
class ProfileUpdateView(UpdateView):
    model = Profile
    form_class = ProfileUpdateForm
    template_name = 'users/profile_update.html'
    success_url = reverse_lazy('users:profile')

    def get_object(self):
        return self.request.user.profile

    def form_valid(self, form):
        messages.success(self.request, 'Profile updated successfully')
        return super().form_valid(form)


@method_decorator(login_required, name='dispatch')
class NotificationPreferencesView(UpdateView):
    model = Profile
    form_class = NotificationPreferencesForm
    template_name = 'users/notification_preferences.html'
    success_url = reverse_lazy('users:profile')

    def get_object(self):
        return self.request.user.profile

    def form_valid(self, form):
        messages.success(self.request, 'Notification preferences updated')
        return super().form_valid(form)


class CustomPasswordChangeView(PasswordChangeView):
    template_name = 'users/password_change.html'
    success_url = reverse_lazy('users:password_change_done')
    form_class = PasswordChangeForm

    def form_valid(self, form):
        messages.success(self.request, 'Password changed successfully')
        return super().form_valid(form)


@method_decorator(login_required, name='dispatch')
class AddressCreateView(CreateView):
    model = Address
    form_class = AddressForm
    template_name = 'users/address_form.html'
    success_url = reverse_lazy('users:account')

    def form_valid(self, form):
        form.instance.user = self.request.user
        if form.cleaned_data.get('is_default'):
            # Unset other default addresses
            Address.objects.filter(user=self.request.user).update(is_default=False)
        messages.success(self.request, 'Address added successfully')
        return super().form_valid(form)


@method_decorator(login_required, name='dispatch')
class AddressUpdateView(UpdateView):
    model = Address
    form_class = AddressForm
    template_name = 'users/address_form.html'
    success_url = reverse_lazy('users:account')

    def get_queryset(self):
        return Address.objects.filter(user=self.request.user)

    def form_valid(self, form):
        if form.cleaned_data.get('is_default'):
            # Unset other default addresses
            Address.objects.filter(user=self.request.user).exclude(pk=self.object.pk).update(is_default=False)
        messages.success(self.request, 'Address updated successfully')
        return super().form_valid(form)


@method_decorator(login_required, name='dispatch')
class AddressDeleteView(DeleteView):
    model = Address
    success_url = reverse_lazy('users:account')
    template_name = 'users/address_confirm_delete.html'

    def get_queryset(self):
        return Address.objects.filter(user=self.request.user)

    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Address deleted successfully')
        return super().delete(request, *args, **kwargs)



@login_required
def set_default_address(request, pk):
    address = Address.objects.get(pk=pk, user=request.user)
    Address.objects.filter(user=request.user).update(is_default=False)
    address.is_default = True
    address.save()
    messages.success(request, 'Default address updated successfully')
    return redirect('users:account')


@login_required
@csrf_exempt
def update_profile_image(request):
    if request.method == 'POST' and request.FILES.get('profile_image'):
        profile = request.user.profile
        profile.profile_image = request.FILES['profile_image']
        profile.save()
        return JsonResponse({
            'success': True,
            'profile_image_url': profile.profile_image.url
        })
    return JsonResponse({'success': False, 'error': 'Invalid request'})


class TermsView(TemplateView):
    template_name = "users/legal/terms.html"
    extra_context = {"effective_date": "2025-01-01"}


class PrivacyView(TemplateView):
    template_name = "users/legal/privacy.html"
    extra_context = {"data_officer": "contact@asai.co.ke"}


class ReturnPolicyView(TemplateView):
    template_name = 'users/legal/return-policy.html'


@method_decorator(login_required, name='dispatch')
class AccountView(TemplateView):
    template_name = "users/account.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        # Get recent orders (last 5)
        orders = Order.objects.filter(user=user).order_by('-created')[:5]

        # Calculate total spent efficiently
        total_spent = Order.objects.filter(
            user=user,
            status='completed'
        ).annotate(
            order_total=ExpressionWrapper(
                Sum(F('items__price') * F('items__quantity')),
                output_field=DecimalField(max_digits=10, decimal_places=2)
            )
        ).aggregate(
            total=Sum('order_total')
        )['total'] or Decimal('0.00')

        # Get last order
        last_order = Order.objects.filter(user=user).order_by('-created').first()

        # Calculate order stats efficiently
        order_stats = Order.objects.filter(user=user).aggregate(
            order_count=Count('id')
        )
        order_count = order_stats['order_count']

        # Calculate average order value
        avg_order = total_spent / order_count if order_count > 0 else Decimal('0.00')

        # Get registration address
        registration_address = {
            'full_name': f"{user.first_name} {user.last_name}",
            'street_address': user.registration_street_address,
            'city': user.registration_city,
            'state': user.registration_state,
            'postal_code': user.registration_postal_code,
            'phone': user.phone_number
        } if user.registration_street_address else None

        context.update({
            'orders': orders,
            'total_spent': total_spent,
            'last_order': last_order.created if last_order else None,
            'avg_order': avg_order,
            'order_count': order_count,
            'registration_address': registration_address,
        })
        return context