# users/views.py
from django.db import IntegrityError
from django.http import HttpResponse
from django.views.decorators.http import require_GET
from django.views.generic import View
from django.contrib.auth import logout as auth_logout, logout
from django.urls import reverse
import uuid
from decimal import Decimal
from .models import ActivityLog
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.urls import reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from .forms import UserRegisterForm, ProfileUpdateForm, NotificationPreferencesForm, AccountDeletionForm
from .forms import AddressForm, PasswordChangeForm
from .models import Profile, Address
from orders.models import Order
from django.contrib.auth import login as auth_login
from django.contrib.auth.views import PasswordChangeView, LoginView
from django.views.generic import TemplateView, UpdateView, CreateView, DeleteView, FormView
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.db.models import Sum, Count

class CustomLoginView(LoginView):
    template_name = 'users/login.html'
    redirect_authenticated_user = True

    def get_success_url(self):
        # Get the 'next' parameter from request
        next_url = self.request.POST.get('next') or self.request.GET.get('next')

        # Validate URL for security
        if next_url and url_has_allowed_host_and_scheme(
                url=next_url,
                allowed_hosts={self.request.get_host()},
                require_https=self.request.is_secure(),
        ):
            return next_url

        # Redirect to product list page after login
        return reverse('store:product_list')

    def form_valid(self, form):
        remember_me = self.request.POST.get('remember_me', False)
        if not remember_me:
            self.request.session.set_expiry(0)
            self.request.session.modified = True

        # Add success message
        messages.success(self.request, 'You have been successfully logged in!')
        return super().form_valid(form)

    def form_invalid(self, form):
        # Add error message for invalid credentials
        messages.error(self.request, 'Invalid credentials. Please try again.')
        return self.render_to_response(self.get_context_data(form=form))


class CustomLogoutView(View):
    next_page = reverse_lazy('users:logout_success')

    def dispatch(self, request, *args, **kwargs):
        if not request.path.startswith(reverse('users:logout')):
            request.session['pre_logout_path'] = request.META.get('HTTP_REFERER', '')
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            ActivityLog.objects.create(
                user=request.user,
                activity_type='logout',
                ip_address=self.get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )

        # Let the signal handle cart preservation
        auth_logout(request)

        return redirect(self.next_page)

    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        return x_forwarded_for.split(',')[0] if x_forwarded_for else request.META.get('REMOTE_ADDR')



class LogoutSuccessView(TemplateView):
    template_name = 'users/logout_success.html'
    http_method_names = ['get']  # Only allow GET requests

    def get(self, request, *args, **kwargs):
        # Just clear user-specific data, preserve cart_id
        user_specific_keys = [
            '_auth_user_id',
            '_auth_user_backend',
            '_auth_user_hash',
            'pre_logout_path',
            'post_logout_redirect'
        ]
        for key in user_specific_keys:
            if key in request.session:
                del request.session[key]

        context = self.get_context_data(**kwargs)
        context['user'] = None

        response = self.render_to_response(context)
        response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'

        return response

def register(request):
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            try:
                user = form.save(commit=False)
                user.save()  # Save user first

                # Create profile if it doesn't exist
                if not hasattr(user, 'profile'):
                    Profile.objects.create(
                        user=user,
                        marketing_optin=form.cleaned_data['marketing_optin']
                    )

                # Authenticate user
                auth_login(
                    request,
                    user,
                    backend='django.contrib.auth.backends.ModelBackend'
                )

                messages.success(request, 'Registration successful! You are now logged in.')
                return redirect('store:product_list')

            except IntegrityError as e:
                # Handle duplicate profile error
                if 'users_profile_user_id_key' in str(e):
                    messages.error(request, 'User already has a profile. Please try again.')
                else:
                    messages.error(request, 'An error occurred during registration. Please try again.')
                return redirect('users:register')

    else:
        form = UserRegisterForm()

    return render(request, 'users/register.html', {
        'form': form,
        'privacy_policy_url': reverse_lazy('users:privacy')
    })


@method_decorator(login_required, name='dispatch')
class ProfileUpdateView(UpdateView):
    model = Profile
    form_class = ProfileUpdateForm
    template_name = 'users/profile_update.html'
    success_url = reverse_lazy('users:account')

    def get_object(self):
        return self.request.user.profile

    def form_valid(self, form):
        messages.success(self.request, 'Profile updated successfully')
        return super().form_valid(form)


@method_decorator(login_required, name='dispatch')
class AccountDeleteView(FormView):
    template_name = 'users/account_delete_confirm.html'
    form_class = AccountDeletionForm
    success_url = reverse_lazy('store:product_list')

    # Fix: Pass user to form
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        user = self.request.user

        # Anonymize personal data (GDPR compliance)
        user.email = f'deleted-{uuid.uuid4()}@example.com'
        user.first_name = 'Deleted'
        user.last_name = 'User'
        user.phone_number = None
        user.set_unusable_password()
        user.is_active = False
        user.save()

        # Anonymize profile
        profile = user.profile
        if profile.profile_image:
            profile.profile_image.delete(save=False)
        profile.bio = ''
        profile.save()

        # Logout user after deletion
        logout(self.request)

        messages.success(self.request, 'Your account has been permanently deleted')
        return super().form_valid(form)


@method_decorator(login_required, name='dispatch')
class NotificationPreferencesView(UpdateView):
    model = Profile
    form_class = NotificationPreferencesForm
    template_name = 'users/notification_preferences.html'
    success_url = reverse_lazy('users:account')

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



@login_required(login_url='/accounts/login/')
def set_default_address(request, pk):
    address = Address.objects.get(pk=pk, user=request.user)
    Address.objects.filter(user=request.user).update(is_default=False)
    address.is_default = True
    address.save()
    messages.success(request, 'Default address updated successfully')
    return redirect('users:account')


@login_required(login_url='/accounts/login/')
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

        # Calculate total spent - use 'total' instead of 'total_amount'
        total_spent = Order.objects.filter(
            user=user,
            status='completed'
        ).aggregate(
            total=Sum('total')  # Changed from 'total_amount'
        )['total'] or Decimal('0.00')

        # Get last order
        last_order = Order.objects.filter(user=user).order_by('-created').first()

        # Calculate order stats
        order_stats = Order.objects.filter(user=user).aggregate(
            order_count=Count('id')
        )
        order_count = order_stats['order_count']

        # Calculate average order value
        avg_order = total_spent / order_count if order_count > 0 else Decimal('0.00')

        context.update({
            'orders': orders,
            'total_spent': total_spent,
            'last_order': last_order.created if last_order else None,
            'avg_order': avg_order,
            'order_count': order_count,
        })
        return context


@require_GET
@csrf_exempt
def session_keepalive(request):
    """Reset session expiry time on any request"""
    if request.session:
        request.session.modified = True
        return HttpResponse(status=204)
    return HttpResponse(status=400)