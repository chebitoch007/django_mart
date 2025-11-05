CATEGORIES = {
    "Gaming Hardware": {
        "Consoles": [],
        "Gaming PCs & Laptops": [],
        "Graphics Cards & Components": [],
    },
    "Gaming Accessories": {
        "Headsets & Microphones": [],
        "Keyboards & Mice": [],
        "Gaming Chairs & Desks": [],
    },
    "Games & Software": {
        "PC Games": [],
        "PlayStation Games": [],
        "Xbox Games": [],
    },
    "Merch & Collectibles": {
        "Apparel & Hoodies": [],
        "Action Figures & Statues": [],
    },
    "Streaming & Content Creation": {
        "Microphones": [],
        "Webcams & Cameras": [],
    },
    "PC Building": {
        "Processors (CPUs)": [],
        "Memory (RAM)": [],
        "Storage (SSDs & HDDs)": [],
    }
}

# ----- Sorting config -----
# note: use review_count_annotation to avoid conflict with Product.review_count field
SORT_OPTIONS = {
    'relevance': {
        'label': 'Relevance',
        'field': ('-rank', '-similarity'),  # ✅ MODIFIED: Use a tuple for multi-field sorting
        'icon': 'fa-search',
    },
    'popular': {
        'label': 'Most Popular',
        'field': '-review_count_annotation',
        'icon': 'fa-fire',
    },
    'newest': {
        'label': 'Newest Arrivals',
        'field': '-created',
        'icon': 'fa-clock',
    },
    'price_low': {
        'label': 'Price: Low to High',
        'field': 'price',
        'icon': 'fa-arrow-down-short-wide',
    },
    'price_high': {
        'label': 'Price: High to Low',
        'field': '-price',
        'icon': 'fa-arrow-up-short-wide',
    },
    'rating': {
        'label': 'Top Rated',
        'field': '-avg_rating',
        'icon': 'fa-star',
    },
    'discount': {
        'label': 'Biggest Discount',
        'field': '-discount_percentage',
        'icon': 'fa-tags',
    },
    'name': {
        'label': 'Name: A–Z',
        'field': 'name',
        'icon': 'fa-font',
    },
}
