
PAYMENT_METHODS = (
    ('CASH', 'Cash on Delivery'),
    ('MOBILE_MONEY', 'Mobile Money'),
    ('MPESA', 'M-Pesa'),
    ('AIRTEL', 'Airtel Money'),
)

ORDER_STATUS_CHOICES = (
    ('PENDING', 'Pending Payment'),
    ('PAID', 'Paid'),
    ('FULFILLED', 'Fulfilled'),
    ('CANCELLED', 'Cancelled'),
)

CURRENCY_CHOICES = (
    ('KES', 'Kenyan Shilling'),
    ('UGX', 'Ugandan Shilling'),
    ('TZS', 'Tanzanian Shilling'),
    ('USD', 'US Dollar'),
    ('GBP', 'British Pound Sterling'),
)