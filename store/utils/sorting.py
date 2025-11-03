# store/utils/sorting.py

from django.db.models import Value, FloatField
from django.db.models import Avg, Count, F, ExpressionWrapper, DecimalField
from django.db.models.functions import Coalesce
from store.constants import SORT_OPTIONS

def get_sorted_products(queryset, sort_key, is_search=False):
    queryset = queryset.annotate(
        avg_rating=Coalesce(Avg('reviews__rating'), 0.0),
        review_count_annotation=Count('reviews'),
    )

    # Prevent relevance sort outside search
    if sort_key == 'relevance' and not is_search:
        sort_key = 'newest'

    sort_option = SORT_OPTIONS.get(sort_key, SORT_OPTIONS['newest'])
    sort_field = sort_option['field']

    # ✅ FIX: If sorting by rank/similarity, ensure they exist
    if sort_key == 'relevance':
        # Check if rank already exists (from search)
        # If not, add default annotations
        if 'rank' not in queryset.query.annotations:
            queryset = queryset.annotate(
                rank=Value(0.0, output_field=FloatField()),
                similarity=Value(0.0, output_field=FloatField())
            )

    # Add discount percentage annotation only if sorting by it
    if sort_field == '-discount_percentage':
        queryset = queryset.annotate(
            discount_percentage=ExpressionWrapper(
                (F('price') - F('discount_price')) / F('price') * 100,
                output_field=DecimalField()
            )
        )

    if isinstance(sort_field, (list, tuple)):
        return queryset.order_by(*sort_field)
    else:
        return queryset.order_by(sort_field)