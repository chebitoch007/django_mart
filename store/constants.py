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
    'price_asc': 'price',
    'price_desc': '-price',
    'name': 'name',
    'rating': '-avg_rating',
    'popular': '-review_count_annotation',     # changed to annotation name
    'newest': '-created',
    'discount': '-discount_percentage',
}