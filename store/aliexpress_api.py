import requests
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


def get_product_details(product_id):
    """Get product details from RapidAPI"""
    url = "https://aliexpress-datahub.p.rapidapi.com/item_detail"
    querystring = {"itemId": product_id}

    headers = {
        "X-RapidAPI-Key": settings.ALIEXPRESS_API_KEY,
        "X-RapidAPI-Host": settings.ALIEXPRESS_API_HOST
    }

    try:
        response = requests.get(url, headers=headers, params=querystring)
        response.raise_for_status()
        return response.json().get('result', {})
    except Exception as e:
        logger.error(f"API request failed: {str(e)}")
        return None


def extract_product_data(api_data):
    """Extract and format product data from API response"""
    if not api_data:
        return None

    return {
        'name': api_data.get('title', ''),
        'description': api_data.get('description', ''),
        'price': float(api_data.get('sku', {}).get('def', {}).get('price', 0)),
        'original_price': float(api_data.get('sku', {}).get('def', {}).get('originalPrice', 0)),
        'image_url': api_data.get('image', [''])[0],
        'gallery_images': api_data.get('image', [])[:5],
        'shipping_time': api_data.get('logisticsInfo', {}).get('shipmentTime', '10-20 days'),
        'product_id': api_data.get('itemId', ''),
        'supplier': api_data.get('store', {}).get('name', 'AliExpress Supplier')
    }