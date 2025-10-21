# store/utils/filters.py
from typing import Iterable, Optional
from django.db.models import Q, Avg, Count
from django.db.models.functions import Coalesce
from django.http import HttpRequest

# Helper to interpret "truthy" GET params
_TRUTHY = {'1', 'true', 'yes', 'on', 't'}

def _is_truthy(value: Optional[str]) -> bool:
    if value is None:
        return False
    return str(value).lower() in _TRUTHY

def _parse_number(value: Optional[str]) -> Optional[float]:
    if not value:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None

def apply_search_filter(request: HttpRequest, queryset):
    """
    Apply standard product filters from request.GET to the given queryset.

    Supported GET params:
      - category     : category slug
      - max_price    : numeric upper bound (price <=)
      - min_price    : numeric lower bound (price >=)
      - in_stock     : truthy -> stock > 0
      - min_rating   : numeric (filters by annotated avg_rating)
      - brand        : brand id or slug or name (prefers numeric id)
      - supplier     : supplier id or name
      - q (ignored here) : leave full-text ranking to the search view
      - any additional params should be added centrally here

    This function returns the filtered queryset (does NOT sort or paginate).
    """
    req = request
    GET = req.GET

    # Category filter (by slug)
    category_slug = GET.get('category')
    if category_slug:
        queryset = queryset.filter(category__slug=category_slug)

    # Price filters
    min_price = _parse_number(GET.get('min_price'))
    if min_price is not None:
        queryset = queryset.filter(price__gte=min_price)

    max_price = _parse_number(GET.get('max_price'))
    if max_price is not None:
        queryset = queryset.filter(price__lte=max_price)

    # Stock / availability
    in_stock = _is_truthy(GET.get('in_stock'))
    if in_stock:
        queryset = queryset.filter(stock__gt=0)

    # Rating filter: use annotation to compute avg rating if not present
    min_rating = _parse_number(GET.get('min_rating'))
    if min_rating is not None:
        # annotate avg_rating only if needed -- safe to annotate each time
        queryset = queryset.annotate(avg_rating=Coalesce(Avg('reviews__rating'), 0.0)).filter(avg_rating__gte=min_rating)

    # Brand: allow numeric id, slug, or name lookup (name uses icontains to be flexible)
    brand = GET.get('brand')
    if brand:
        brand = brand.strip()
        if brand.isdigit():
            queryset = queryset.filter(brand_id=int(brand))
        else:
            # try slug first (exact), then name (icontains)
            queryset = queryset.filter(Q(brand__slug__iexact=brand) | Q(brand__name__icontains=brand))

    # Supplier: allow numeric id or name lookup
    supplier = GET.get('supplier')
    if supplier:
        supplier = supplier.strip()
        if supplier.isdigit():
            queryset = queryset.filter(supplier_id=int(supplier))
        else:
            # supplier may be stored as normalized supplier.name or older supplier_name text
            queryset = queryset.filter(
                Q(supplier__name__icontains=supplier) |
                Q(supplier_name__icontains=supplier)
            )

    # Expose ability to filter by 'available' flag explicitly (optional)
    available = GET.get('available')
    if available is not None:
        # Interpret common truthy/falsy values; default to boolean check only if provided
        if _is_truthy(available):
            queryset = queryset.filter(available=True)
        else:
            queryset = queryset.filter(available=False)

    # If you want to prevent N+1 later, caller/view should add select_related/prefetch_related as needed.
    return queryset


# alias used in your views (the view you showed calls apply_product_filters)
apply_product_filters = apply_search_filter
