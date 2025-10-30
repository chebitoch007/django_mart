# store/utils/search.py

from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank
from django.contrib.postgres.search import TrigramSimilarity
from django.db.models.functions import Greatest, Coalesce
from django.db.models import Q, Value, CharField

SEARCH_WEIGHTS = [0.0, 0.1, 0.3, 0.6]
RANK_THRESHOLD = 0.1
TRIGRAM_THRESHOLD = 0.15


def apply_search_filter(queryset, query):
    """
    Safe + fast text search for PostgreSQL.
    Handles NULL supplier/brand gracefully.
    """
    if not query:
        return queryset.none()

    search_query = SearchQuery(query, search_type='plain', config='english')

    # Use Coalesce to handle NULL foreign keys safely
    vector = (
        SearchVector('name', weight='A', config='english') +
        SearchVector('short_description', weight='B', config='english') +
        SearchVector('description', weight='B', config='english') +
        SearchVector(
            Coalesce('category__name', Value('')),
            weight='C',
            config='english'
        ) +
        SearchVector(
            Coalesce('brand__name', Value('')),
            weight='C',
            config='english'
        ) +
        SearchVector(
            Coalesce('supplier__name', Value('')),
            weight='C',
            config='english'
        )
    )

    queryset = queryset.annotate(
        rank=SearchRank(vector, search_query, weights=SEARCH_WEIGHTS),
        similarity=Greatest(
            TrigramSimilarity('name', query),
            TrigramSimilarity('short_description', query),
            TrigramSimilarity('description', query),
            TrigramSimilarity(Coalesce('category__name', Value('')), query),
            TrigramSimilarity(Coalesce('brand__name', Value('')), query),
            TrigramSimilarity(Coalesce('supplier__name', Value('')), query),
        ),
    ).filter(
        Q(rank__gte=RANK_THRESHOLD) | Q(similarity__gte=TRIGRAM_THRESHOLD),
        available=True
    ).order_by('-rank', '-similarity')

    return queryset