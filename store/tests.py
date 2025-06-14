from django.test import TestCase, Client
from django.utils import timezone
from datetime import timedelta
from .models import NewsletterSubscription


class NewsletterTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.valid_email = 'test@example.com'

    def test_full_subscription_flow(self):
        # Test valid subscription
        response = self.client.post('/subscribe/', {'email': self.valid_email})
        self.assertContains(response, 'confirmation email sent')
        sub = NewsletterSubscription.objects.get()
        self.assertFalse(sub.confirmed)

        # Test confirmation
        self.client.get(f'/confirm-subscription/{sub.confirmation_token}/')
        sub.refresh_from_db()
        self.assertTrue(sub.confirmed)

        # Test unsubscribe
        self.client.get(f'/unsubscribe/{sub.unsubscribe_token}/')
        sub.refresh_from_db()
        self.assertTrue(sub.unsubscribed)

    def test_duplicate_subscription(self):
        self.client.post('/subscribe/', {'email': self.valid_email})
        response = self.client.post('/subscribe/', {'email': self.valid_email})
        self.assertContains(response, 'already subscribed')

    def test_expired_confirmation(self):
        sub = NewsletterSubscription.objects.create(
            email=self.valid_email,
            confirmation_token='test',
            confirmation_sent=timezone.now() - timedelta(days=2))
        self.client.get(f'/confirm-subscription/{sub.confirmation_token}/')
        self.assertEqual(NewsletterSubscription.objects.count(), 0)

    def test_invalid_unsubscribe(self):
        response = self.client.get('/unsubscribe/invalid-token/')
        self.assertContains(response, 'Invalid unsubscribe link')
