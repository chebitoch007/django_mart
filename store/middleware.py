from django.conf import settings


class CurrencyMiddleware:
    """
    Middleware to set default currency in session if not present.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Set default currency if not in session
        if 'user_currency' not in request.session:
            request.session['user_currency'] = settings.DEFAULT_CURRENCY

        response = self.get_response(request)
        return response
