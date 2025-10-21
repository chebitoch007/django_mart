# store/utils/search.py

from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank
from django.contrib.postgres.search import TrigramSimilarity
from django.db.models.functions import Greatest
from django.db.models import Q

SEARCH_WEIGHTS = {
    'A': 0.6,
    'B': 0.3,
    'C': 0.1,
}
RANK_THRESHOLD = 0.1
TRIGRAM_THRESHOLD = 0.15


def apply_search_filter(queryset, query):
    """Safe + fast text search for PostgreSQL."""
    if not query:
        return queryset.none()

    search_query = SearchQuery(query, search_type='plain', config='english')

    vector = (
        SearchVector('name', weight='A', config='english') +
        SearchVector('short_description', weight='B', config='english') +
        SearchVector('description', weight='B', config='english') +
        SearchVector('category__name', weight='C', config='english') +
        SearchVector('supplier', weight='C', config='english')  # ✅ FIXED
    )

    queryset = queryset.annotate(
        rank=SearchRank(vector, search_query, weights=SEARCH_WEIGHTS),
        similarity=Greatest(
            TrigramSimilarity('name', query),
            TrigramSimilarity('short_description', query),
            TrigramSimilarity('description', query),
            TrigramSimilarity('category__name', query),
            TrigramSimilarity('supplier', query),  # ✅ FIXED
        ),
    ).filter(
        Q(rank__gte=RANK_THRESHOLD) | Q(similarity__gte=TRIGRAM_THRESHOLD),
        available=True
    ).order_by('-rank', '-similarity')

    return queryset
