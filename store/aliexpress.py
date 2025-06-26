import requests
from django.conf import settings

ALIEXPRESS_API_KEY = getattr(settings, 'ALIEXPRESS_API_KEY', 'your-api-key')


def get_aliexpress_product_details(product_url):
    """Fetch AliExpress product details from URL"""
    # Extract product ID from URL
    import re
    match = re.search(r'/(\d+)\.html', product_url)
    if not match:
        return None

    product_id = match.group(1)

    # Use AliExpress Affiliate API (example)
    params = {
        'app_key': ALIEXPRESS_API_KEY,
        'productId': product_id,
        'fields': 'title,imageUrl,price,commissionRate'
    }

    try:
        response = requests.get(
            'https://api.affiliate.ali.com/products/details',
            params=params
        )
        data = response.json()

        return {
            'name': data.get('title'),
            'image_url': data.get('imageUrl'),
            'price': float(data.get('price')),
            'commission': float(data.get('commissionRate'))
        }
    except:
        return None


def generate_affiliate_link(product_url):
    """Convert regular AliExpress link to affiliate link"""
    return f"https://s.click.aliexpress.com/deep_link.htm?aff_short_key={ALIEXPRESS_API_KEY}&url={product_url}"