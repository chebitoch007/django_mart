import re
from django.core.exceptions import ValidationError


def validate_product_name(value):
    if len(value) < 5 or len(value) > 100:
        raise ValidationError('Product name must be 5-100 characters long')

    # More permissive regex allowing common punctuation
    if not re.match(r'^[\w\s\-\'",.()&!;:%+@#°*¢£¥€©®™]+$', value):
        raise ValidationError('Product name contains invalid characters')