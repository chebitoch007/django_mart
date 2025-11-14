# users/utils.py - Enhanced Address utility functions

from django.utils import timezone
from typing import Optional, Dict, Any
from django.contrib.auth import get_user_model
from .models import Address, ActivityLog
from .views import get_client_ip

User = get_user_model()


def get_unique_address_nickname(user: User, desired_nickname: str) -> str:
    """
    Generate a unique address nickname for a user.
    If the desired nickname exists, append a number.

    Args:
        user: User instance
        desired_nickname: The nickname the user wants to use

    Returns:
        A unique nickname string
    """
    if not desired_nickname:
        # Generate a default nickname
        count = Address.objects.filter(user=user).count()
        return f"Address {count + 1}"

    # Check if nickname is already unique
    if not Address.objects.filter(
            user=user,
            nickname__iexact=desired_nickname.strip()
    ).exists():
        return desired_nickname.strip()

    # Generate unique nickname by appending numbers
    base_nickname = desired_nickname.strip()
    counter = 1

    while True:
        new_nickname = f"{base_nickname} {counter}"
        if not Address.objects.filter(
                user=user,
                nickname__iexact=new_nickname
        ).exists():
            return new_nickname
        counter += 1

        # Safety check to prevent infinite loop
        if counter > 100:
            import uuid
            return f"{base_nickname} {uuid.uuid4().hex[:6]}"


def get_user_default_address(user: User) -> Optional[Address]:
    """
    Get user's default address or most recent address.

    Args:
        user: User instance

    Returns:
        Address instance or None
    """
    if not user.is_authenticated:
        return None

    # Try to get default address first
    default_address = Address.objects.filter(
        user=user,
        is_default=True
    ).first()

    if default_address:
        return default_address

    # Fallback to most recent address
    return Address.objects.filter(
        user=user
    ).order_by('-created').first()


def create_address_from_order_data(user: User, order_data: Dict[str, Any],
                                   nickname: str = None,
                                   is_default: bool = False) -> Optional[Address]:
    """
    Create a new address from order form data.
    Handles duplicate checking and nickname conflicts.

    Args:
        user: User instance
        order_data: Dictionary containing address fields from order
        nickname: Optional nickname for the address
        is_default: Whether to set as default address

    Returns:
        Created Address instance or None if duplicate exists
    """
    # Check for exact duplicate first
    existing = duplicate_address_check(
        user,
        order_data.get('address', ''),
        order_data.get('city', ''),
        order_data.get('postal_code', '')
    )

    if existing:
        return None  # Don't create duplicate

    # Generate unique nickname
    if not nickname:
        nickname = "New Address"

    unique_nickname = get_unique_address_nickname(user, nickname)

    # Determine address type from nickname
    address_type = 'shipping'
    nickname_lower = unique_nickname.lower()
    if 'home' in nickname_lower:
        address_type = 'home'
    elif 'work' in nickname_lower or 'office' in nickname_lower:
        address_type = 'work'
    elif 'bill' in nickname_lower:
        address_type = 'billing'

    # If is_default is True, unset other default addresses
    if is_default:
        Address.objects.filter(user=user, is_default=True).update(is_default=False)
    elif not Address.objects.filter(user=user).exists():
        # First address is automatically default
        is_default = True

    # Create the address
    address = Address.objects.create(
        user=user,
        nickname=unique_nickname,
        address_type=address_type,
        full_name=f"{order_data.get('first_name', '')} {order_data.get('last_name', '')}".strip(),
        street_address=order_data.get('address', ''),
        city=order_data.get('city', ''),
        state=order_data.get('state', ''),
        postal_code=order_data.get('postal_code', ''),
        country=order_data.get('country', 'KE'),
        phone=order_data.get('phone', ''),
        is_default=is_default
    )

    return address


def populate_order_from_address(order_instance, address: Address) -> None:
    """
    Populate order fields from an address instance.

    Args:
        order_instance: Order model instance (not yet saved)
        address: Address instance to copy from
    """
    # Split full name if possible
    name_parts = address.full_name.split(maxsplit=1)
    order_instance.first_name = name_parts[0] if name_parts else ''
    order_instance.last_name = name_parts[1] if len(name_parts) > 1 else ''

    # Copy address fields
    order_instance.address = address.street_address
    order_instance.city = address.city
    order_instance.state = address.state
    order_instance.postal_code = address.postal_code
    order_instance.country = address.country
    order_instance.phone = address.phone


def sync_address_with_user_profile(user: User, address: Address) -> None:
    """
    Optionally sync a primary address with user profile fields.
    Useful for keeping user profile in sync with their default address.

    Args:
        user: User instance
        address: Address to sync from
    """
    if not hasattr(user, 'profile'):
        return

    profile = user.profile

    # Update phone if not set on user
    if address.phone and not user.phone_number:
        user.phone_number = address.phone
        user.save(update_fields=['phone_number'])


def get_address_summary(address: Address) -> str:
    """
    Get a one-line summary of an address for display.

    Args:
        address: Address instance

    Returns:
        String summary of address
    """
    parts = [
        address.street_address,
        address.city,
        address.state,
        address.postal_code,
        str(address.country.name) if hasattr(address.country, 'name') else str(address.country)
    ]

    # Filter out empty parts
    parts = [p for p in parts if p]

    return ', '.join(parts)


def validate_address_completeness(address: Address) -> tuple[bool, list[str]]:
    """
    Validate that an address has all required fields.

    Args:
        address: Address instance to validate

    Returns:
        Tuple of (is_valid, list_of_missing_fields)
    """
    required_fields = {
        'full_name': 'Full name',
        'street_address': 'Street address',
        'city': 'City',
        'postal_code': 'Postal code',
        'country': 'Country'
    }

    missing = []

    for field, label in required_fields.items():
        value = getattr(address, field, None)
        if not value or (isinstance(value, str) and not value.strip()):
            missing.append(label)

    return len(missing) == 0, missing


def duplicate_address_check(user: User, street_address: str, city: str,
                            postal_code: str) -> Optional[Address]:
    """
    Check if user already has this address saved.

    Args:
        user: User instance
        street_address: Street address to check
        city: City to check
        postal_code: Postal code to check

    Returns:
        Existing Address instance if found, None otherwise
    """
    return Address.objects.filter(
        user=user,
        street_address__iexact=street_address.strip(),
        city__iexact=city.strip(),
        postal_code__iexact=postal_code.strip()
    ).first()


def merge_duplicate_addresses(user: User) -> int:
    """
    Find and merge duplicate addresses for a user.
    Keeps the oldest address and deletes duplicates.

    Args:
        user: User instance

    Returns:
        Number of addresses merged/deleted
    """
    from django.db.models import Count

    # Find addresses with duplicate locations
    addresses = Address.objects.filter(user=user).order_by('created')

    seen = {}
    to_delete = []

    for address in addresses:
        key = (
            address.street_address.lower().strip(),
            address.city.lower().strip(),
            address.postal_code.strip()
        )

        if key in seen:
            # This is a duplicate
            to_delete.append(address.id)
        else:
            seen[key] = address

    # Delete duplicates
    if to_delete:
        Address.objects.filter(id__in=to_delete).delete()

    return len(to_delete)


def log_profile_change(user, request, changed_fields):
    """
    Helper function to log profile changes with detailed information.

    Args:
        user: User instance
        request: HttpRequest object
        changed_fields: Dictionary of changed fields with old/new values

    Returns:
        ActivityLog instance
    """
    return ActivityLog.objects.create(
        user=user,
        activity_type='profile_update',
        ip_address=get_client_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', ''),
        additional_info={
            'changed_fields': list(changed_fields.keys()),
            'changes': changed_fields,
            'timestamp': timezone.now().isoformat()
        }
    )