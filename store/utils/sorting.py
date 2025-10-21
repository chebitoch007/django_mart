from store.constants import SORT_OPTIONS
from django.db.models import Avg, Count, F, ExpressionWrapper, DecimalField
from django.db.models.functions import Coalesce

# ----- Helpers ----- #
def get_sorted_products(queryset, sort_key):
    """
    Annotate safely (no conflicting names) and order.
    """
    # annotate using unique names that don't overlap model fields
    queryset = queryset.annotate(
        avg_rating=Coalesce(Avg('reviews__rating'), 0.0),
        review_count_annotation=Count('reviews'),  # safe alias
    )

    # annotate discount only when needed
    if sort_key == 'discount':
        queryset = queryset.annotate(
            discount_percentage=ExpressionWrapper(
                (F('price') - F('discount_price')) / F('price') * 100,
                output_field=DecimalField()
            )
        )

    sort_field = SORT_OPTIONS.get(sort_key, '-created')
    return queryset.order_by(sort_field)