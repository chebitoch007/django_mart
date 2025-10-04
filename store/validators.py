# store/validators.py
import re
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


def validate_product_name(value):
    """
    Validates product names with comprehensive checks and user-friendly messages
    """
    # Length validation
    if len(value) < 5 or len(value) > 100:
        raise ValidationError(_('Product name must be between 5 and 100 characters'))

    # Character whitelist validation
    allowed_chars = r"a-zA-Z0-9\s\-'\"\.,\(\)&!;:%+@#°*¢£¥€©®™"
    pattern = f"^[{allowed_chars}]+$"

    if not re.match(pattern, value):
        # Provide specific feedback about invalid characters
        invalid_chars = set(re.findall(f"[^{allowed_chars}]", value))
        invalid_list = ", ".join(sorted(f"'{c}'" for c in invalid_chars))

        raise ValidationError(
            _('Invalid characters found: %(invalid_chars)s. Only letters, numbers, spaces, and common punctuation are allowed.'),
            params={'invalid_chars': invalid_list},
            code='invalid_chars'
        )

    # Prevent problematic patterns
    if re.search(r"\s{3,}", value):  # Multiple consecutive spaces
        raise ValidationError(_('Too many consecutive spaces'))

    if value.startswith((' ', '-', '.', ',')) or value.endswith((' ', '-', '.', ',')):
        raise ValidationError(_('Name cannot start or end with space, hyphen, period, or comma'))

    return value