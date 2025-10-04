import uuid
import re
import requests
import time
import random
import logging
import json
from bs4 import BeautifulSoup
from django.core.files.base import ContentFile
from django.utils.text import slugify
from django.conf import settings
from django.db import transaction
from store.models import Product, Category, ProductImage

# Initialize logger
logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
]


def get_random_headers():
    return {
        'User-Agent': random.choice(USER_AGENTS),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'TE': 'Trailers',
    }


def validate_image_url(url):
    """Check if URL is valid for image download"""
    if not url or not url.startswith('http'):
        return False
    return any(url.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.webp'])


def download_image(url):
    """Download image with retries and validation"""
    if not validate_image_url(url):
        logger.warning(f"Invalid image URL: {url}")
        return None, None

    for attempt in range(3):
        try:
            # Use our random headers for image downloads too
            response = requests.get(url, headers=get_random_headers(), timeout=15)
            response.raise_for_status()

            # Generate unique filename
            ext = url.split('.')[-1].lower()
            if ext not in ['jpg', 'jpeg', 'png', 'webp']:
                ext = 'jpg'

            file_name = f"{uuid.uuid4().hex}.{ext}"
            return ContentFile(response.content), file_name
        except Exception as e:
            logger.warning(f"Image download failed (attempt {attempt + 1}): {str(e)}")
            time.sleep(2)
    return None, None


def extract_from_script_data(soup):
    """Extract product data from JSON in script tags"""
    scripts = soup.find_all('script')
    for script in scripts:
        if script.string and 'window.runParams' in script.string:
            try:
                # Extract JSON data from script
                match = re.search(r'window\.runParams\s*=\s*({.*?});', script.string, re.DOTALL)
                if match:
                    json_str = match.group(1)
                    data = json.loads(json_str)

                    # Extract relevant data
                    page_module = data.get('pageModule', {})
                    price_module = data.get('priceModule', {})
                    desc_module = data.get('descModule', {})
                    image_module = data.get('imageModule', {})
                    shipping_module = data.get('shippingModule', {})

                    return {
                        'name': page_module.get('productName', ''),
                        'description': desc_module.get('description', ''),
                        'price': float(
                            price_module.get('formatedActivityPrice', '0').replace('$', '').replace(',', '')),
                        'original_price': float(
                            price_module.get('formatedPrice', '0').replace('$', '').replace(',', '')),
                        'image_url': image_module.get('imagePathList', [''])[0] if image_module.get(
                            'imagePathList') else '',
                        'gallery_images': image_module.get('imagePathList', [])[1:6],
                        'shipping_time': shipping_module.get('deliveryDateMsg', '10-20 days'),
                        'product_id': page_module.get('productId', ''),
                        'supplier': data.get('storeModule', {}).get('storeName', 'AliExpress Supplier')
                    }
            except Exception as e:
                logger.error(f"Error extracting data from script: {str(e)}")
    return None


def scrape_product_details(url):
    """Robust scraping with JSON extraction and modern selectors"""
    try:
        time.sleep(random.uniform(1.5, 3.0))
        response = requests.get(url, headers=get_random_headers(), timeout=30)
        response.raise_for_status()

        if response.status_code == 403:
            raise Exception("Access denied. Please try again later.")

        soup = BeautifulSoup(response.content, 'html.parser')

        # First try to extract data from JSON in scripts
        json_data = extract_from_script_data(soup)
        if json_data:
            logger.info("Extracted product data from JSON script")
            return json_data

        # Fallback to manual scraping if JSON extraction failed
        logger.info("Falling back to manual scraping")

        # Product name
        name_tag = soup.select_one('h1.product-title-text')
        name = name_tag.text.strip() if name_tag else "Product Name"

        # Description
        description = ""
        desc_tag = soup.select_one('.detail-desc')
        if not desc_tag:
            desc_tag = soup.select_one('.product-description')
        if desc_tag:
            # Remove unnecessary elements
            for tag in desc_tag.select('script, style, noscript, .comet-optin'):
                tag.decompose()
            description = desc_tag.get_text(separator='\n', strip=True)

        if not description:
            description = "No description available"

        # Prices
        price = 0.0
        original_price = 0.0

        # Try to get prices from meta tags
        price_meta = soup.select_one('meta[itemprop="price"]')
        if price_meta and 'content' in price_meta.attrs:
            try:
                price = float(price_meta['content'])
            except ValueError:
                pass

        original_price_meta = soup.select_one('meta[itemprop="originalPrice"]')
        if original_price_meta and 'content' in original_price_meta.attrs:
            try:
                original_price = float(original_price_meta['content'])
            except ValueError:
                pass

        # If meta tags failed, try visible elements
        if price <= 0:
            price_tag = soup.select_one('.product-price-value, .uniform-banner-box-price')
            if price_tag:
                try:
                    price = float(price_tag.text.strip().replace('$', '').replace(',', ''))
                except ValueError:
                    pass

        if original_price <= 0:
            original_price_tag = soup.select_one('.product-price-original, .original-price')
            if original_price_tag:
                try:
                    original_price = float(original_price_tag.text.strip().replace('$', '').replace(',', ''))
                except ValueError:
                    pass

        if original_price <= 0:
            original_price = price

        # Images
        image_url = ""
        gallery_images = []

        # Try to get from gallery
        gallery_tags = soup.select('.images-view-item img, .thumb-item img')
        if gallery_tags:
            for img in gallery_tags[:6]:  # Get up to 6 images
                if 'src' in img.attrs:
                    img_url = img['src']
                    if 'http' not in img_url:
                        img_url = 'https:' + img_url
                    if image_url == "":
                        image_url = img_url
                    else:
                        gallery_images.append(img_url)

        # If no gallery images, try main image
        if not image_url:
            image_tag = soup.select_one('.magnifier-image, .main-img')
            if image_tag and 'src' in image_tag.attrs:
                image_url = image_tag['src']
                if 'http' not in image_url:
                    image_url = 'https:' + image_url

        # Shipping
        shipping_time = "10-20 days"
        shipping_tag = soup.select_one('.product-shipping-time, .delivery-option')
        if shipping_tag:
            shipping_time = shipping_tag.text.strip()

        # Product ID
        product_id = ""
        product_id_match = re.search(r'/(\d+)\.html', url)
        if product_id_match:
            product_id = product_id_match.group(1)

        return {
            'name': name,
            'description': description,
            'price': price,
            'original_price': original_price,
            'image_url': image_url,
            'gallery_images': gallery_images,
            'shipping_time': shipping_time,
            'product_id': product_id,
            'url': url,
            'supplier': "AliExpress Supplier"
        }

    except Exception as e:
        logger.error(f"Scraping error for {url}: {str(e)}", exc_info=True)
        return None


def get_aliexpress_product_details(url):
    """Get product details via scraping"""
    logger.info(f"Scraping product: {url}")
    product_data = scrape_product_details(url)

    if product_data:
        logger.info(f"Successfully scraped product: {product_data['name']}")
        return product_data

    logger.warning(f"Scraping failed for: {url}")
    return None


def generate_affiliate_link(product_url):
    """Generate affiliate link with tracking"""
    if not hasattr(settings, 'ALIEXPRESS_TRACKING_ID'):
        return product_url

    return f"{product_url}?af=YOUR_AFFILIATE_ID&aff_trace_key={settings.ALIEXPRESS_TRACKING_ID}"


def import_aliexpress_product(url, category_slug):
    """Full product import with transaction safety"""
    try:
        logger.info(f"Starting import: {url}")
        product_data = get_aliexpress_product_details(url)
        if not product_data:
            return None, "Failed to fetch product details"

        logger.info(f"Product data retrieved: {product_data['name']}")

        # Create/get category
        slug = slugify(category_slug)
        category, created = Category.objects.get_or_create(
            slug=slug,
            defaults={'name': category_slug}
        )

        # Prepare product data
        short_description = product_data['description'][:200] + "..." if product_data['description'] else ""
        commission_rate = 15.0

        # Create product in transaction
        with transaction.atomic():
            product = Product.objects.create(
                category=category,
                name=product_data['name'][:200],
                description=product_data['description'],
                short_description=short_description,
                price=product_data['price'],
                discount_price=product_data['original_price'],
                stock=100,
                available=True,
                is_dropship=True,
                supplier=product_data.get('supplier', 'AliExpress Supplier'),
                supplier_url=url,
                supplier_product_id=product_data.get('product_id', ''),
                shipping_time=product_data['shipping_time'],
                commission_rate=commission_rate
            )

            # Download main image
            if product_data['image_url']:
                img_content, img_name = download_image(product_data['image_url'])
                if img_content:
                    product.image.save(img_name, img_content, save=True)
                else:
                    logger.warning(f"Failed to download main image for {product_data['name']}")

            # Download additional images
            image_urls = product_data.get('gallery_images', [])
            for img_url in image_urls[:5]:  # Max 5 additional images
                img_content, img_name = download_image(img_url)
                if img_content:
                    ProductImage.objects.create(
                        product=product,
                        image=img_name,
                        image_file=img_content
                    )
                else:
                    logger.warning(f"Failed to download gallery image: {img_url}")

        logger.info(f"Product imported: {product.name} (ID: {product.id})")
        return product, "Success"

    except Exception as e:
        logger.error(f"Import failed: {str(e)}", exc_info=True)
        return None, str(e)


def fulfill_order(order_item):
    try:
        product = order_item.product
        if not product.is_dropship:
            return False, "Not a dropshipping product"

        # Simulate order processing
        tracking_number = f"TRACK-{uuid.uuid4().hex[:12]}"
        estimated_delivery = product.shipping_time

        # Update order item
        order_item.tracking_number = tracking_number
        order_item.estimated_delivery = estimated_delivery
        order_item.dropship_processed = True
        order_item.save()

        # Generate affiliate link
        affiliate_link = generate_affiliate_link(product.supplier_url)

        # In a real scenario, you would:
        # 1. Open the affiliate link in a browser
        # 2. Manually place the order on AliExpress
        # 3. Enter the real tracking number in admin
        logger.info(f"SIMULATED fulfillment for order item {order_item.id}")
        logger.info(f"Product URL: {product.supplier_url}")
        logger.info(f"Affiliate link: {affiliate_link}")

        return True, f"Tracking: {tracking_number}"

    except Exception as e:
        logger.error(f"Fulfillment simulation failed: {str(e)}")
        return False, str(e)