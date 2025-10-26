CATEGORIES = {
    "Electronics": {
        "Audio & Headphones": [],
        "Mobile Accessories": [],
        "Computers & Laptops": [],
        "Cameras & Photography": [],
        "TV & Home Theater": [],
        "Wearable Technology": [],
        "Gaming Consoles": [],
        "Smart Home Devices": [],
    },
    "Gaming Accessories": {
        "Controllers & Input Devices": [],
        "Headsets & Audio": [],
        "Charging Stations": [],
        "Protective Cases": [],
        "Display Enhancements": [],
        "Console Skins & Decals": [],
        "Gaming Chairs": [],
        "VR Accessories": [],
    },
    "Home & Kitchen": {
        "Small Appliances": [],
        "Cookware & Bakeware": [],
        "Home Decor": [],
        "Kitchen Utensils": [],
        "Storage & Organization": [],
        "Lighting Solutions": [],
    },
    "Fashion": {
        "Men's Clothing": [],
        "Women's Clothing": [],
        "Shoes & Footwear": [],
        "Accessories": [],
        "Watches & Jewelry": [],
        "Bags & Luggage": [],
    },
    "Health & Beauty": {
        "Skincare": [],
        "Hair Care": [],
        "Makeup & Cosmetics": [],
        "Fragrances": [],
        "Personal Care": [],
        "Health Devices": [],
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
