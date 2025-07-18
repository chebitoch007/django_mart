import hmac
import hashlib
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.http import HttpResponseForbidden, HttpResponse


class WebhookSecurity:
    @staticmethod
    def verify_hmac_signature(request):
        """Verify HMAC signature for webhook requests"""
        signature = request.headers.get('X-Signature')
        if not signature:
            return False

        # Use provider-specific secret from settings
        provider = request.headers.get('X-Provider')
        secret = getattr(settings, f"{provider.upper()}_WEBHOOK_SECRET", None)

        if not secret:
            return False

        expected_signature = hmac.new(
            secret.encode(),
            request.body,
            hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(signature, expected_signature)

    @staticmethod
    @csrf_exempt
    @require_POST
    def secure_webhook_view(view_func):
        """Decorator for secure webhook handling"""

        def wrapper(request, *args, **kwargs):
            if not WebhookSecurity.verify_hmac_signature(request):
                return HttpResponseForbidden("Invalid signature")
            return view_func(request, *args, **kwargs)

        return wrapper