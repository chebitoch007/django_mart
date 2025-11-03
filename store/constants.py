CATEGORIES = {
    "Gaming Hardware": {
        "Consoles": [],
        "Gaming PCs & Laptops": [],
        "Graphics Cards & Components": [],
        "Monitors & Displays": [],
        "Controllers & Input Devices": [],
        "VR Headsets & Accessories": [],
    },
    "Gaming Accessories": {
        "Headsets & Microphones": [],
        "Keyboards & Mice": [],
        "Gaming Chairs & Desks": [],
        "Mousepads & Mats": [],
        "Console Skins & Decals": [],
        "Charging Docks & Stands": [],
        "Cable Management": [],
        "Cooling Pads & Fans": [],
    },
    "Games & Software": {
        "PC Games": [],
        "PlayStation Games": [],
        "Xbox Games": [],
        "Nintendo Games": [],
        "VR Games": [],
        "Game Passes & Gift Cards": [],
        "DLCs & In-Game Currency": [],
    },
    "Merch & Collectibles": {
        "Apparel & Hoodies": [],
        "Action Figures & Statues": [],
        "Posters & Art Prints": [],
        "Mugs & Drinkware": [],
        "Keychains & Badges": [],
        "Limited Editions & Memorabilia": [],
    },
    "Streaming & Content Creation": {
        "Microphones": [],
        "Webcams & Cameras": [],
        "Capture Cards": [],
        "Lighting & Green Screens": [],
        "Streaming Software & Tools": [],
        "Mounts & Tripods": [],
    },
    "PC Building": {
        "Processors (CPUs)": [],
        "Motherboards": [],
        "Memory (RAM)": [],
        "Storage (SSDs & HDDs)": [],
        "Power Supplies (PSUs)": [],
        "Cases & Cooling": [],
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
