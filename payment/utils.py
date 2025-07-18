def get_prioritized_payment_methods(request):
    country = getattr(request, 'country', None)

    if country == 'KE':
        return ['mpesa', 'airtel', 'card', 'paypal']
    elif country in ['US', 'GB', 'CA', 'AU']:
        return ['card', 'paypal', 'mpesa', 'airtel']
    else:
        return ['paypal', 'card', 'mpesa', 'airtel']


def get_currency_options():
    return [
        {'code': 'KES', 'name': 'Kenyan Shilling'},
        {'code': 'USD', 'name': 'US Dollar'},
        {'code': 'EUR', 'name': 'Euro'},
        {'code': 'GBP', 'name': 'British Pound'},
    ]
