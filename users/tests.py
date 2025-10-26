from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from .models import Profile, Address
from unittest.mock import patch  # <-- 1. IMPORT PATCH

# Get the CustomUser model
User = get_user_model()


class UserModelTest(TestCase):
    """Tests for the CustomUser model and manager."""

    def test_create_user(self):
        # ... (no changes in this test) ...
        user = User.objects.create_user(
            email='test@example.com',
            password='ValidPassword1!',
            first_name='Test',
            last_name='User'
        )
        self.assertEqual(user.email, 'test@example.com')
        self.assertEqual(user.first_name, 'Test')
        self.assertTrue(user.check_password('ValidPassword1!'))
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertFalse(hasattr(user, 'profile'))

    def test_create_superuser(self):
        # ... (no changes in this test) ...
        admin_user = User.objects.create_superuser(
            email='admin@example.com',
            password='ValidPassword1!',
            first_name='Admin',
            last_name='User'
        )
        self.assertEqual(admin_user.email, 'admin@example.com')
        self.assertTrue(admin_user.is_staff)
        self.assertTrue(admin_user.is_superuser)

    def test_create_user_no_email_fails(self):
        # ... (no changes in this test) ...
        with self.assertRaises(ValueError):
            User.objects.create_user(email=None, password='ValidPassword1!')

    def test_password_validation_fails(self):
        # ... (no changes in this test) ...
        with self.assertRaises(ValidationError):
            User.objects.create_user(
                email='weak@pass.com',
                password='short',  # Fails length, upper, digit, special
                first_name='Weak',
                last_name='Pass'
            )

    def test_password_history_created(self):
        """Test that changing a password adds to the PasswordHistory."""
        user = User.objects.create_user(
            email='history@example.com',
            password='ValidPassword1!',
            first_name='Test',
            last_name='User'
        )
        # 2. FIX: On create, password history is 0 (user.pk is None)
        self.assertEqual(user.password_history.count(), 0)

        user.set_password('NewValidPassword2@')
        # 1st change
        self.assertEqual(user.password_history.count(), 1)

        user.set_password('AnotherValidPassword3#')
        # 2nd change
        self.assertEqual(user.password_history.count(), 2)


class RegistrationViewTest(TestCase):
    """Tests for the user registration view."""

    def setUp(self):
        self.register_url = reverse('users:register')

    def test_register_view_get(self):
        # ... (no changes in this test) ...
        response = self.client.get(self.register_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'users/register.html')
        self.assertRegex(response.content.decode(), r'Create (Your|an) Account')

    # 3. FIX: Add mock patch for reCAPTCHA
    @patch('users.forms._validate_recaptcha', return_value=True)
    def test_register_success_with_marketing_optin(self, mock_validate_recaptcha):
        """Test successful registration with marketing opt-in."""
        data = {
            'first_name': 'New',
            'last_name': 'User',
            'email': 'newuser@example.com',
            'password1': 'ValidPassword1!',
            'password2': 'ValidPassword1!',
            'accept_terms': True,
            'marketing_optin': True,
        }

        response = self.client.post(self.register_url, data)

        # Should redirect to the store
        self.assertRedirects(response, reverse('store:product_list'))

        # Check that user and profile were created
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(Profile.objects.count(), 1)

        user = User.objects.get(email='newuser@example.com')
        self.assertEqual(user.first_name, 'New')

        # ** CRITICAL TEST: Verify the bugfix for marketing_optin **
        self.assertTrue(hasattr(user, 'profile'))
        self.assertTrue(user.profile.marketing_optin)

        # Check that the user is automatically logged in
        self.assertIn('_auth_user_id', self.client.session)
        self.assertEqual(self.client.session['_auth_user_id'], str(user.id))

    # 3. FIX: Add mock patch for reCAPTCHA
    @patch('users.forms._validate_recaptcha', return_value=True)
    def test_register_success_no_marketing_optin(self, mock_validate_recaptcha):
        """Test successful registration without marketing opt-in."""
        data = {
            'first_name': 'NoMarket',
            'last_name': 'User',
            'email': 'nomarket@example.com',
            'password1': 'ValidPassword1!',
            'password2': 'ValidPassword1!',
            'accept_terms': True,
            # 'marketing_optin' is False by default when not checked
        }
        response = self.client.post(self.register_url, data)

        self.assertEqual(response.status_code, 302)
        user = User.objects.get(email='nomarket@example.com')

        # ** CRITICAL TEST: Verify marketing_optin is False **
        self.assertTrue(hasattr(user, 'profile'))
        self.assertFalse(user.profile.marketing_optin)

    # 3. FIX: Add mock patch for reCAPTCHA
    @patch('users.forms._validate_recaptcha', return_value=True)
    def test_register_duplicate_email(self, mock_validate_recaptcha):
        """Test registration with an email that already exists."""
        User.objects.create_user(
            email='test@example.com',
            password='ValidPassword1!',
            first_name='Test',
            last_name='User'
        )
        data = {
            'first_name': 'Another',
            'last_name': 'User',
            'email': 'test@example.com',  # Duplicate email
            'password1': 'ValidPassword1!',
            'password2': 'ValidPassword1!',
            'accept_terms': True,
        }
        response = self.client.post(self.register_url, data)

        # Should re-render the form with an error
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'An account with this email already exists')
        self.assertEqual(User.objects.count(), 1)  # No new user created

    # 3. FIX: Add mock patch for reCAPTCHA
    @patch('users.forms._validate_recaptcha', return_value=True)
    def test_register_password_mismatch(self, mock_validate_recaptcha):
        """Test registration with mismatched passwords."""
        data = {
            'first_name': 'New',
            'last_name': 'User',
            'email': 'newuser@example.com',
            'password1': 'ValidPassword1!',
            'password2': 'DIFFERENTPassword1!',
            'accept_terms': True,
        }
        response = self.client.post(self.register_url, data)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Passwords don't match")  # Note HTML escaping
        self.assertEqual(User.objects.count(), 0)


class AuthenticationViewTest(TestCase):
    # ... (no changes in this class) ...
    def setUp(self):
        self.user = User.objects.create_user(
            email='login@example.com',
            password='ValidPassword1!',
            first_name='Login',
            last_name='User'
        )
        self.login_url = reverse('users:login')
        self.logout_url = reverse('users:logout')

    def test_login_success_with_email(self):
        response = self.client.post(self.login_url, {
            'username': 'login@example.com',  # Form field is 'username'
            'password': 'ValidPassword1!'
        })
        self.assertRedirects(response, reverse('store:product_list'))
        self.assertIn('_auth_user_id', self.client.session)
        self.assertEqual(self.client.session['_auth_user_id'], str(self.user.id))

    def test_login_fail_wrong_password(self):
        response = self.client.post(self.login_url, {
            'username': 'login@example.com',
            'password': 'WrongPassword1!'
        })
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'users/login.html')
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertContains(response, 'Invalid credentials')  # Custom message

    def test_login_fail_nonexistent_user(self):
        response = self.client.post(self.login_url, {
            'username': 'nosuchuser@example.com',
            'password': 'ValidPassword1!'
        })
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'users/login.html')
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertContains(response, 'Invalid credentials')

    def test_logout_success(self):
        self.client.login(email='login@example.com', password='ValidPassword1!')
        self.assertIn('_auth_user_id', self.client.session)

        response = self.client.post(self.logout_url)  # Logout is POST
        self.assertRedirects(response, reverse('users:logout_success'))
        self.assertNotIn('_auth_user_id', self.client.session)


class AccountViewTest(TestCase):
    # ... (no changes in this class) ...
    def setUp(self):
        self.user = User.objects.create_user(
            email='account@example.com',
            password='ValidPassword1!',
            first_name='Account',
            last_name='User'
        )
        # Manually create profile, assuming signals are (correctly) removed
        self.profile = Profile.objects.create(user=self.user, dark_mode=False)

        self.client = Client()
        self.client.login(email='account@example.com', password='ValidPassword1!')

        self.account_url = reverse('users:account')
        self.profile_update_url = reverse('users:profile_update')
        self.add_address_url = reverse('users:add_address')

    def test_account_view_get(self):
        response = self.client.get(self.account_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'users/account.html')
        self.assertContains(response, 'Account User')
        self.assertContains(response, 'Add New Address')

    def test_profile_update_view_post(self):
        data = {
            # UserProfileForm fields
            'first_name': 'Updated',
            'last_name': 'Name',
            'phone_number': '+254712345678',
            'email': 'account@example.com',  # Email from UserProfileForm

            # ProfileUpdateForm fields
            'email_notifications': False,
            'sms_notifications': True,
            'preferred_language': 'en',
            'dark_mode': True,
        }
        response = self.client.post(self.profile_update_url, data)
        self.assertRedirects(response, self.account_url)

        # Verify changes in the database
        self.user.refresh_from_db()
        self.profile.refresh_from_db()

        self.assertEqual(self.user.first_name, 'Updated')
        self.assertEqual(self.user.phone_number, '+254712345678')
        self.assertTrue(self.profile.dark_mode)
        self.assertFalse(self.profile.email_notifications)

    def test_address_create_view_post(self):
        data = {
            'nickname': 'Home',
            'address_type': 'shipping',  # ADD THIS LINE
            'full_name': 'Account User',
            'street_address': '123 Test St',
            'city': 'Nairobi',
            'state': 'Nairobi',
            'postal_code': '00100',
            'country': 'KE',
            'phone': '+254712345678',
            'is_default': True
        }

        response = self.client.post(self.add_address_url, data)
        self.assertRedirects(response, self.account_url)

        self.assertEqual(Address.objects.count(), 1)
        address = Address.objects.first()
        self.assertEqual(address.user, self.user)
        self.assertEqual(address.city, 'Nairobi')
        self.assertTrue(address.is_default)

    def test_address_update_and_delete(self):
        address = Address.objects.create(
            user=self.user,
            nickname='Work',
            address_type='work',  # ADD THIS LINE
            full_name='Account User',
            street_address='456 Office Rd',
            city='Nairobi',
            state='Nairobi',
            postal_code='00200',
            country='KE'
        )

        # --- Test Update ---
        update_url = reverse('users:edit_address', kwargs={'pk': address.pk})
        update_data = {
            'nickname': 'Work',
            'address_type': 'work',
            'full_name': 'Account User',
            'street_address': '789 New Office Rd',  # Changed
            'city': 'Mombasa',  # Changed
            'state': 'Mombasa',
            'postal_code': '00200',
            'country': 'KE',  # ✅ CHANGED: Use country code instead of 'Kenya'
        }
        response = self.client.post(update_url, update_data)
        self.assertRedirects(response, self.account_url)

        address.refresh_from_db()
        self.assertEqual(address.city, 'Mombasa')
        self.assertEqual(address.street_address, '789 New Office Rd')

        # --- Test Delete ---
        delete_url = reverse('users:delete_address', kwargs={'pk': address.pk})
        response = self.client.post(delete_url)  # Deletion is a POST
        self.assertRedirects(response, self.account_url)

        self.assertEqual(Address.objects.count(), 0)


class AccountDeletionTest(TestCase):
    """Tests the AccountDeletionView for security and functionality."""

    def setUp(self):
        self.user = User.objects.create_user(
            email='delete@example.com',
            password='ValidPassword1!',
            first_name='Delete',
            last_name='Me'
        )
        # 4. FIX: Create the profile that the view expects to find
        self.profile = Profile.objects.create(user=self.user)

        self.client = Client()
        self.client.login(email='delete@example.com', password='ValidPassword1!')
        self.delete_url = reverse('users:account_delete')

    def test_delete_fail_wrong_password(self):
        # ... (no changes in this test) ...
        data = {
            'confirm': True,
            'password': 'WrongPassword1!'
        }
        response = self.client.post(self.delete_url, data)

        self.assertEqual(response.status_code, 200)  # Re-renders form
        self.assertTemplateUsed(response, 'users/account_delete_confirm.html')
        self.assertContains(response, 'Your password was entered incorrectly')

        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)  # User is still active

    def test_delete_success(self):
        # ... (no changes in this test) ...
        data = {
            'confirm': True,
            'password': 'ValidPassword1!'  # Correct password
        }
        response = self.client.post(self.delete_url, data)

        self.assertRedirects(response, reverse('store:product_list'))

        # Check user is "anonymized" and inactive
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)
        self.assertNotEqual(self.user.email, 'delete@example.com')
        self.assertEqual(self.user.first_name, 'Deleted')
        self.assertFalse(self.user.has_usable_password())

        # Check user is logged out
        self.assertNotIn('_auth_user_id', self.client.session)

