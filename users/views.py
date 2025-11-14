# users/views.py

from django.db import transaction
from django.core.mail import send_mail
from django.template.loader import render_to_string
from .forms import UnifiedProfileForm
from django.core.exceptions import ValidationError
from django.contrib.auth.tokens import default_token_generator
from django.contrib.sessions.models import Session
from django.utils import timezone
import logging  # For logging
from django.conf import settings  # For ALLOWED_HOSTS
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit # For rate limiting
from django.contrib.auth import views as auth_views
from django.contrib.auth.views import PasswordResetView as AuthPasswordResetView
from django.contrib.auth.forms import PasswordResetForm
import json
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
# IMPORT UserProfileForm, REMOVE NotificationPreferencesForm
from .forms import UserRegisterForm, AccountDeletionForm
from .forms import AddressForm, PasswordChangeForm
from .models import Profile, Address
from orders.models import Order
from django.contrib.auth import login as auth_login
from django.contrib.auth.views import PasswordChangeView, LoginView
from django.views.generic import TemplateView, UpdateView, CreateView, DeleteView, FormView
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from django.http import JsonResponse
from django.db.models import Sum, Count
from django.views.decorators.http import require_http_methods

# Setup logger
logger = logging.getLogger(__name__)


def get_client_ip(request):
    """Helper to get the client's IP address."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


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


def send_phone_change_notification(user, old_phone, new_phone, request):
    """
    Send email notification when phone number is changed.
    Security measure to alert user of account changes.
    """
    try:
        context = {
            'user': user,
            'old_phone': old_phone or 'Not set',
            'new_phone': new_phone,
            'ip_address': get_client_ip(request),
            'user_agent': request.META.get('HTTP_USER_AGENT', 'Unknown'),
            'timestamp': timezone.now()
        }

        subject = 'Phone Number Changed on Your Account'
        html_message = render_to_string('users/emails/phone_change_notification.html', context)
        plain_message = f"""
        Hello {user.get_full_name()},

        Your phone number has been changed.

        Old number: {old_phone or 'Not set'}
        New number: {new_phone}

        If you did not make this change, please contact support immediately.

        IP Address: {context['ip_address']}
        Time: {context['timestamp']}
        """

        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=True  # Don't break if email fails
        )

        logger.info(f"Phone change notification sent to {user.email}")
    except Exception as e:
        logger.error(f"Failed to send phone change notification: {str(e)}")


@login_required
@transaction.atomic  # Ensure all-or-nothing database updates
def profile_update_view(request):
    """
    Unified profile update view handling both User and Profile models.

    Features:
    - Single form for all profile data
    - Atomic transactions
    - Activity logging
    - Phone change notifications
    - Real-time validation
    - AJAX support for image operations
    """

    # Ensure profile exists
    profile, created = Profile.objects.select_for_update().get_or_create(user=request.user)

    if request.method == 'POST':
        form = UnifiedProfileForm(request.POST, request.FILES, user=request.user)

        if form.is_valid():
            try:
                # Save form data
                user, profile, changed_fields = form.save(commit=True)

                # Log activity with changed fields
                if changed_fields:
                    ActivityLog.objects.create(
                        user=user,
                        activity_type='profile_update',
                        ip_address=get_client_ip(request),
                        user_agent=request.META.get('HTTP_USER_AGENT', ''),
                        additional_info={
                            'changed_fields': list(changed_fields.keys()),
                            'changes': changed_fields
                        }
                    )

                    logger.info(
                        f"Profile updated for {user.email}. "
                        f"Changed fields: {', '.join(changed_fields.keys())}"
                    )

                # Send notification if phone number changed
                if form.has_phone_changed():
                    old_phone = form.original_phone
                    new_phone = form.cleaned_data.get('phone_number')

                    # Send email notification (async in production)
                    send_phone_change_notification(user, old_phone, new_phone, request)

                    # Log phone change specifically
                    ActivityLog.objects.create(
                        user=user,
                        activity_type='profile_update',
                        ip_address=get_client_ip(request),
                        user_agent=request.META.get('HTTP_USER_AGENT', ''),
                        additional_info={
                            'change_type': 'phone_number',
                            'old_value': old_phone,
                            'new_value': new_phone
                        }
                    )

                # Success message
                messages.success(
                    request,
                    'Your profile has been updated successfully!'
                )

                # Redirect to account page
                return redirect('users:account')

            except Exception as e:
                logger.error(
                    f"Error updating profile for {request.user.email}: {str(e)}",
                    exc_info=True
                )
                messages.error(
                    request,
                    'An error occurred while updating your profile. Please try again.'
                )
                # Rollback happens automatically due to @transaction.atomic
        else:
            # Form validation failed
            messages.error(
                request,
                'Please correct the errors below.'
            )
            logger.warning(
                f"Profile update validation failed for {request.user.email}: "
                f"{form.errors.as_json()}"
            )
    else:
        # GET request - display form with current data
        form = UnifiedProfileForm(user=request.user)

    context = {
        'form': form,
        'profile': profile,
        'has_custom_image': bool(profile.profile_image)
    }

    return render(request, 'users/profile_update.html', context)


@require_http_methods(["POST"])
@login_required
@transaction.atomic
def ajax_update_profile_image(request):
    """
    AJAX endpoint for updating profile image.
    Allows real-time image upload without full form submission.

    Returns JSON with success status and new image URL.
    """
    try:
        if not request.FILES.get('profile_image'):
            return JsonResponse({
                'success': False,
                'error': 'No image file provided'
            }, status=400)

        # Get or create profile
        profile = Profile.objects.select_for_update().get(user=request.user)

        # Validate image using form field validator
        from .forms import UnifiedProfileForm
        form = UnifiedProfileForm(user=request.user)

        # Create a temporary form to validate just the image
        image_file = request.FILES['profile_image']

        # Manual validation
        try:
            # Use form's clean_profile_image method
            form.fields['profile_image'].clean(image_file)
        except ValidationError as e:
            return JsonResponse({
                'success': False,
                'error': str(e.message)
            }, status=400)

        # Delete old image if exists
        if profile.profile_image:
            try:
                profile.profile_image.delete(save=False)
            except Exception as e:
                logger.warning(f"Could not delete old profile image: {e}")

        # Save new image
        profile.profile_image = image_file
        profile.save(update_fields=['profile_image', 'last_updated'])

        # Log activity
        ActivityLog.objects.create(
            user=request.user,
            activity_type='profile_update',
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            additional_info={'action': 'profile_image_upload'}
        )

        logger.info(f"Profile image updated for {request.user.email}")

        return JsonResponse({
            'success': True,
            'profile_image_url': profile.profile_image.url,
            'message': 'Profile image updated successfully'
        })

    except Profile.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Profile not found'
        }, status=404)
    except Exception as e:
        logger.error(
            f"Error updating profile image for {request.user.email}: {str(e)}",
            exc_info=True
        )
        return JsonResponse({
            'success': False,
            'error': 'An error occurred while uploading the image'
        }, status=500)


@require_http_methods(["POST"])
@login_required
@transaction.atomic
def ajax_remove_profile_image(request):
    """
    AJAX endpoint for removing profile image.
    Sets profile image to None, reverting to default.

    Returns JSON with success status.
    """
    try:
        profile = Profile.objects.select_for_update().get(user=request.user)

        # Check if there's a custom image to remove
        if not profile.profile_image:
            return JsonResponse({
                'success': False,
                'error': 'No custom profile picture to remove'
            }, status=400)

        # Delete the image file
        try:
            profile.profile_image.delete(save=False)
        except Exception as e:
            logger.warning(f"Could not delete profile image file: {e}")

        # Clear the profile_image field
        profile.profile_image = None
        profile.save(update_fields=['profile_image', 'last_updated'])

        # Log activity
        ActivityLog.objects.create(
            user=request.user,
            activity_type='profile_update',
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            additional_info={'action': 'profile_image_removed'}
        )

        logger.info(f"Profile image removed for {request.user.email}")

        return JsonResponse({
            'success': True,
            'message': 'Profile picture removed successfully'
        })

    except Profile.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Profile not found'
        }, status=404)
    except Exception as e:
        logger.error(
            f"Error removing profile image for {request.user.email}: {str(e)}",
            exc_info=True
        )
        return JsonResponse({
            'success': False,
            'error': 'An error occurred while removing the image'
        }, status=500)

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
        profile, _ = Profile.objects.get_or_create(user=user)
        if profile.profile_image:
            profile.profile_image.delete(save=False)
        profile.bio = ''
        profile.save()

        # Logout user after deletion
        logout(self.request)

        messages.success(self.request, 'Your account has been permanently deleted')
        return super().form_valid(form)


# REMOVED NotificationPreferencesView - its functionality is merged into profile_update_view


class CustomPasswordChangeView(PasswordChangeView):
    template_name = 'users/password_change.html'
    success_url = reverse_lazy('users:password_change_done')
    form_class = PasswordChangeForm

    def form_valid(self, form):
        messages.success(self.request, 'Password changed successfully')
        return super().form_valid(form)


# --- HARDENED PASSWORD RESET VIEWS ---

@method_decorator(ratelimit(key='ip', rate='5/h', block=True), name='dispatch')  # Rate limit by IP
class CustomPasswordResetView(AuthPasswordResetView):
    template_name = 'users/password_reset.html'
    email_template_name = 'users/password_reset_email.html'
    subject_template_name = 'users/password_reset_subject.txt'
    success_url = reverse_lazy('users:password_reset_done')

    def form_valid(self, form):
        email = form.cleaned_data['email']
        self.request.session['password_reset_email'] = email
        logger.debug("Storing email in session for resend: %s", email)

        domain = get_safe_domain(self.request)

        opts = {
            'use_https': self.request.is_secure(),
            #'domain_override': domain,
            'email_template_name': self.email_template_name,
            'subject_template_name': self.subject_template_name,
            'request': self.request,
            # Use the default token generator explicitly
            'token_generator': default_token_generator,
            # Use configured DEFAULT_FROM_EMAIL if provided
            'from_email': getattr(settings, 'DEFAULT_FROM_EMAIL', None),
        }

        # send email
        form.save(**opts)

        return redirect(self.get_success_url())



@method_decorator(ratelimit(key='ip', rate='10/h', block=True), name='dispatch')  # Rate limit by IP
class CustomPasswordResetConfirmView(auth_views.PasswordResetConfirmView):
    template_name = 'users/password_reset_confirm.html'
    success_url = reverse_lazy('users:password_reset_complete')

    def form_valid(self, form):
        # Save the new password; returns the user instance in Django's implementation
        user = form.save()

        # Log the event
        try:
            ActivityLog.objects.create(
                user=user,
                activity_type='password_reset',
                ip_address=get_client_ip(self.request),
                user_agent=self.request.META.get('HTTP_USER_AGENT', '')
            )
            logger.info("Password reset logged for %s", user.email)
        except Exception as e:
            logger.exception("Failed to log password reset: %s", e)

        # Invalidate ALL sessions for this user, including other devices
        delete_all_user_sessions(user)

        # Optionally, create a fresh session for this request user if you want them
        # to be automatically logged in after reset: auth_login(self.request, user)
        # But for security, you may prefer to require user to log in manually. Adjust as needed.

        messages.success(self.request, "Your password has been successfully reset.")
        return redirect(self.get_success_url())


# --- END HARDENED VIEWS ---


@csrf_protect
@ratelimit(key='ip', rate='5/h', block=True)
def resend_password_reset_email(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid request method.'}, status=405)

    try:
        data = {}
        if request.body:
            try:
                data = json.loads(request.body)
            except json.JSONDecodeError:
                # If it's form data, use POST
                data = request.POST.dict()

        email = data.get('email') or request.session.get('password_reset_email')
        logger.debug("Resend password reset using email: %s", email)

        if not email:
            return JsonResponse({'success': False, 'message': 'No email address found.'}, status=400)

        form = PasswordResetForm({'email': email})
        if not form.is_valid():
            logger.debug("PasswordResetForm invalid for email: %s", email)
            return JsonResponse({'success': False, 'message': 'Invalid email address.'}, status=400)

        domain = get_safe_domain(request)

        opts = {
            'use_https': request.is_secure(),
            #'domain_override': domain,
            'token_generator': default_token_generator,
            'from_email': getattr(settings, 'DEFAULT_FROM_EMAIL', None),
            'email_template_name': 'users/password_reset_email.html',
            'subject_template_name': 'users/password_reset_subject.txt',
            'request': request,
        }

        form.save(**opts)
        request.session['password_reset_email'] = email
        logger.info("Password reset email resent to: %s", email)
        return JsonResponse({'success': True, 'message': 'Password reset email has been resent successfully.'})

    except Exception as e:
        logger.exception("Error in resend_password_reset_email: %s", e)
        return JsonResponse({'success': False, 'message': 'An error occurred. Please try again.'}, status=500)


@method_decorator(login_required, name='dispatch')
class AddressCreateView(CreateView):
    """View for creating a new address."""
    model = Address
    form_class = AddressForm
    template_name = 'users/address_form.html'
    success_url = reverse_lazy('users:account')

    def get_form_kwargs(self):
        """Pass user to form for validation."""
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        """Handle valid form submission."""
        try:
            address = form.save(commit=False)
            address.user = self.request.user

            # Auto-assign default address_type if not provided
            if not address.address_type:
                address.address_type = 'shipping'

            # Handle default address toggle
            if address.is_default:
                Address.objects.filter(user=self.request.user).update(is_default=False)
            elif not Address.objects.filter(user=self.request.user).exists():
                # First address is automatically default
                address.is_default = True

            address.save()

            messages.success(
                self.request,
                f'Address "{address.nickname or "New Address"}" added successfully.'
            )
            return redirect(self.success_url)

        except Exception as e:
            logger.error(f"Error creating address: {str(e)}", exc_info=True)
            messages.error(
                self.request,
                'An error occurred while saving the address. Please try again.'
            )
            return self.form_invalid(form)

    def form_invalid(self, form):
        """Handle invalid form submission."""
        logger.warning(f"Address create form errors: {form.errors.as_json()}")
        messages.error(self.request, 'Please correct the errors below.')
        return self.render_to_response(self.get_context_data(form=form))


@method_decorator(login_required, name='dispatch')
class AddressUpdateView(UpdateView):
    """View for updating an existing address."""
    model = Address
    form_class = AddressForm
    template_name = 'users/address_form.html'
    success_url = reverse_lazy('users:account')

    def get_queryset(self):
        """Ensure users can only edit their own addresses."""
        return Address.objects.filter(user=self.request.user)

    def get_form_kwargs(self):
        """Pass user to form for validation."""
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        """Handle valid form submission."""
        try:
            address = form.save(commit=False)

            # Auto-assign default address_type if not provided
            if not address.address_type:
                address.address_type = 'shipping'

            # Handle default address toggle
            if address.is_default:
                # Unset other default addresses
                Address.objects.filter(user=self.request.user).exclude(
                    pk=address.pk
                ).update(is_default=False)

            address.save()

            messages.success(
                self.request,
                f'Address "{address.nickname or "Address"}" updated successfully.'
            )
            return redirect(self.success_url)

        except Exception as e:
            logger.error(f"Error updating address {address.pk}: {str(e)}", exc_info=True)
            messages.error(
                self.request,
                'An error occurred while updating the address. Please try again.'
            )
            return self.form_invalid(form)

    def form_invalid(self, form):
        """Handle invalid form submission."""
        logger.warning(f"Address update form errors: {form.errors.as_json()}")
        messages.error(self.request, 'Please correct the errors below.')
        return self.render_to_response(self.get_context_data(form=form))


@method_decorator(login_required, name='dispatch')
class AddressDeleteView(DeleteView):
    """View for deleting an address."""
    model = Address
    template_name = 'users/address_confirm_delete.html'
    success_url = reverse_lazy('users:account')

    def get_queryset(self):
        """Ensure users can only delete their own addresses."""
        return Address.objects.filter(user=self.request.user)

    def delete(self, request, *args, **kwargs):
        """Handle address deletion."""
        self.object = self.get_object()
        address_name = self.object.nickname or "Address"

        # Check if this is the default address
        was_default = self.object.is_default

        try:
            self.object.delete()

            # If deleted address was default, set another as default
            if was_default:
                new_default = Address.objects.filter(user=request.user).first()
                if new_default:
                    new_default.is_default = True
                    new_default.save()

            messages.success(request, f'Address "{address_name}" deleted successfully.')

        except Exception as e:
            logger.error(f"Error deleting address: {str(e)}", exc_info=True)
            messages.error(request, 'An error occurred while deleting the address.')

        return redirect(self.success_url)


@login_required
def set_default_address(request, pk):
    """Set an address as the default address for the user."""
    try:
        address = Address.objects.get(pk=pk, user=request.user)

        # Unset all other default addresses
        Address.objects.filter(user=request.user).update(is_default=False)

        # Set this address as default
        address.is_default = True
        address.save()

        messages.success(
            request,
            f'"{address.nickname or "Address"}" is now your default address.'
        )

    except Address.DoesNotExist:
        logger.warning(f"User {request.user.id} tried to set non-existent address {pk} as default")
        messages.error(request, 'Address not found.')
    except Exception as e:
        logger.error(f"Error setting default address: {str(e)}", exc_info=True)
        messages.error(request, 'An error occurred. Please try again.')

    return redirect('users:account')


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

        # Get user addresses - ensure proper ordering
        addresses = Address.objects.filter(user=user).order_by('-is_default', '-created')

        # Get recent orders (last 5) - only select_related available fields
        orders = Order.objects.filter(user=user).select_related(
            'user',
            'payment'
        ).prefetch_related(
            'items__product'
        ).order_by('-created')[:5]

        # Calculate total spent - use 'total' field from Order model
        total_spent = Order.objects.filter(
            user=user,
            status__in=['completed', 'paid', 'COMPLETED', 'PAID']  # Handle both cases
        ).aggregate(
            total=Sum('total')
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
            'addresses': addresses,
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



def get_safe_domain(request):
    """
    Return a safe domain (with port if applicable) for password reset URLs.
    """
    host = request.get_host()  # e.g. 'localhost:8000'
    allowed = set(settings.ALLOWED_HOSTS or [])

    if url_has_allowed_host_and_scheme(
        url=host, allowed_hosts=allowed, require_https=request.is_secure()
    ):
        return host

    if settings.ALLOWED_HOSTS:
        first = settings.ALLOWED_HOSTS[0]
        if first and first != '*':
            return first

    # Final fallback — include port if running in dev
    return 'localhost:8000'


def delete_all_user_sessions(user):
    """
    Invalidate all sessions for a user by scanning Session objects and deleting those
    that contain the user's _auth_user_id in session_data.
    """
    try:
        sessions = Session.objects.filter(expire_date__gte=timezone.now())
        user_pk_str = str(user.pk)
        for s in sessions:
            data = s.get_decoded()
            if data.get('_auth_user_id') == user_pk_str:
                s.delete()
    except Exception as e:
        logger.exception("Error deleting user sessions: %s", e)


@login_required
def export_profile_data(request):
    '''
    Export user's profile data in JSON format (GDPR compliance).
    Allows users to download all their personal information.
    '''
    user = request.user
    profile = getattr(user, 'profile', None)

    data = {
        'user_info': {
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'phone_number': user.phone_number,
            'date_joined': user.date_joined.isoformat() if user.date_joined else None,
        },
        'profile': {
            'bio': profile.bio if profile else '',
            'date_of_birth': profile.date_of_birth.isoformat() if profile and profile.date_of_birth else None,
            'preferred_language': profile.preferred_language if profile else '',
            'email_notifications': profile.email_notifications if profile else True,
            'sms_notifications': profile.sms_notifications if profile else False,
            'marketing_optin': profile.marketing_optin if profile else False,
        },
        'addresses': [
            {
                'nickname': addr.nickname,
                'street': addr.street_address,
                'city': addr.city,
                'country': str(addr.country),
            }
            for addr in user.addresses.all()
        ],
        'activity_logs': [
            {
                'activity': log.activity_type,
                'timestamp': log.timestamp.isoformat(),
            }
            for log in user.activities.order_by('-timestamp')[:50]
        ]
    }

    response = HttpResponse(
        json.dumps(data, indent=2),
        content_type='application/json'
    )
    response['Content-Disposition'] = f'attachment; filename="profile_data_{user.id}.json"'

    # Log the data export
    ActivityLog.objects.create(
        user=user,
        activity_type='profile_update',
        ip_address=get_client_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', ''),
        additional_info={'action': 'data_export'}
    )

    return response