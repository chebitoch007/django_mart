#orders/constants.py

PAYMENT_METHODS = (
    ('MPESA', 'M-Pesa'),
    ('PAYPAL', 'PayPal'),
)

ORDER_STATUS_CHOICES = (
    ('PENDING', 'Pending Payment'),
    ('PROCESSING', 'Processing'),
    ('PAID', 'Paid'),
    ('COMPLETED', 'Completed'),
    ('FULFILLED', 'Fulfilled'),
    ('FAILED', 'Failed'),
    ('CANCELLED', 'Cancelled'),
)

CURRENCY_CHOICES = (
    ('KES', 'Kenyan Shilling'),
    ('UGX', 'Ugandan Shilling'),
    ('TZS', 'Tanzanian Shilling'),
    ('USD', 'US Dollar'),
    ('GBP', 'British Pound Sterling'),
)