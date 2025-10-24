# store/utils/sorting.py

from django.db.models import Avg, Count, F, ExpressionWrapper, DecimalField
from django.db.models.functions import Coalesce
from store.constants import SORT_OPTIONS

def get_sorted_products(queryset, sort_key):
    queryset = queryset.annotate(
        avg_rating=Coalesce(Avg('reviews__rating'), 0.0),
        review_count_annotation=Count('reviews'),
    )

    # Add discount percentage annotation for sorting
    if sort_key == 'discount':
        queryset = queryset.annotate(
            discount_percentage=ExpressionWrapper(
                (F('price') - F('discount_price')) / F('price') * 100,
                output_field=DecimalField()
            )
        )

    # ✅ Extract field name safely
    sort_option = SORT_OPTIONS.get(sort_key, SORT_OPTIONS['newest'])
    sort_field = sort_option['field']

    return queryset.order_by(sort_field)
