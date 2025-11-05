# store/aliexpress.py - IMPROVED VERSION WITH BETTER DEBUGGING

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
from store.models import Product, Category, ProductImage, Supplier

logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
]


def get_random_headers():
    return {
        'User-Agent': random.choice(USER_AGENTS),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Cache-Control': 'max-age=0',
    }


def debug_save_html(html_content, filename='debug_page.html'):
    """Save HTML content for debugging purposes"""
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(html_content)
        logger.info(f"✅ Saved debug HTML to {filename}")
    except Exception as e:
        logger.error(f"❌ Failed to save debug HTML: {e}")


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
            response = requests.get(url, headers=get_random_headers(), timeout=15)
            response.raise_for_status()

            ext = url.split('.')[-1].split('?')[0].lower()
            if ext not in ['jpg', 'jpeg', 'png', 'webp']:
                ext = 'jpg'

            file_name = f"{uuid.uuid4().hex}.{ext}"
            return ContentFile(response.content), file_name
        except Exception as e:
            logger.warning(f"Image download failed (attempt {attempt + 1}): {str(e)}")
            time.sleep(2)
    return None, None


def extract_from_script_data(soup):
    """Extract product data from JSON in script tags - IMPROVED"""
    scripts = soup.find_all('script')

    logger.info(f"🔍 Found {len(scripts)} script tags to analyze")

    for idx, script in enumerate(scripts):
        if not script.string:
            continue

        # Try multiple patterns
        patterns = [
            (r'window\.runParams\s*=\s*({.*?});', 'runParams'),
            (r'data:\s*({.*?})\s*}\s*,\s*csrfToken', 'data-csrfToken'),
            (r'window\._init_data_\s*=\s*({.*?});', '_init_data_'),
            (r'__INITIAL_STATE__\s*=\s*({.*?});', 'INITIAL_STATE'),
        ]

        for pattern, pattern_name in patterns:
            match = re.search(pattern, script.string, re.DOTALL)
            if match:
                try:
                    json_str = match.group(1)
                    data = json.loads(json_str)

                    # Try to extract data
                    result = extract_product_info(data)
                    if result and result.get('name'):
                        logger.info(f"✅ Extracted from JSON pattern '{pattern_name}'")
                        logger.info(f"   Product: {result['name'][:60]}")
                        logger.info(f"   Price: ${result['price']}")
                        return result
                except json.JSONDecodeError as e:
                    logger.debug(f"JSON decode failed for pattern '{pattern_name}': {e}")
                except Exception as e:
                    logger.debug(f"Failed to parse pattern '{pattern_name}': {e}")

    logger.warning("⚠️ No valid JSON data found in any script tag")
    return None


def extract_product_info(data):
    """Extract product info from various JSON structures"""
    result = {
        'name': '',
        'description': '',
        'price': 0.0,
        'original_price': 0.0,
        'image_url': '',
        'gallery_images': [],
        'shipping_time': '10-20 days',
        'product_id': '',
        'supplier': 'AliExpress Supplier'
    }

    # Debug: Log the top-level keys
    logger.debug(f"JSON keys: {list(data.keys())[:10]}")

    # Try multiple data structures
    if 'pageModule' in data:
        result['name'] = data['pageModule'].get('title', '')
        result['product_id'] = str(data['pageModule'].get('productId', ''))
        logger.debug(f"Found pageModule: {result['name'][:50]}")

    if 'titleModule' in data:
        result['name'] = data['titleModule'].get('subject', result['name'])
        logger.debug(f"Found titleModule: {result['name'][:50]}")

    if 'priceModule' in data:
        price_data = data['priceModule']
        result['price'] = float(str(price_data.get('minActivityAmount', {}).get('value', 0)))
        result['original_price'] = float(str(price_data.get('minAmount', {}).get('value', 0)))
        logger.debug(f"Found priceModule: ${result['price']}")

    if 'descriptionModule' in data:
        result['description'] = data['descriptionModule'].get('descriptionUrl', '')

    if 'imageModule' in data:
        images = data['imageModule'].get('imagePathList', [])
        if images:
            result['image_url'] = images[0]
            result['gallery_images'] = images[1:6]
            logger.debug(f"Found {len(images)} images")

    if 'shippingModule' in data:
        result['shipping_time'] = data['shippingModule'].get('generalFreightInfo', {}).get('time', '10-20 days')

    if 'storeModule' in data:
        result['supplier'] = data['storeModule'].get('storeName', 'AliExpress Supplier')

    # Validate we got at least a name
    if not result['name']:
        logger.error("❌ Could not extract product name from JSON")
        return None

    return result


def scrape_product_details(url):
    """Robust scraping with multiple fallbacks and debugging"""
    try:
        logger.info(f"🚀 Starting scrape: {url}")

        time.sleep(random.uniform(2.0, 4.0))
        response = requests.get(url, headers=get_random_headers(), timeout=30)
        response.raise_for_status()

        logger.info(f"✅ Got response: {response.status_code}, Length: {len(response.content)} bytes")

        # Check for blocking
        if response.status_code == 403:
            logger.error("❌ Access denied (403). IP may be rate-limited.")
            return None

        if 'captcha' in response.text.lower():
            logger.error("❌ CAPTCHA detected - scraping blocked")
            return None

        # Save HTML for debugging
        debug_save_html(response.text, f'debug_aliexpress_{int(time.time())}.html')

        soup = BeautifulSoup(response.content, 'html.parser')

        # Try JSON extraction first
        json_data = extract_from_script_data(soup)
        if json_data and json_data.get('name'):
            logger.info(f"✅ Successfully extracted from JSON")
            return json_data

        logger.warning("⚠️ JSON extraction failed, trying HTML parsing...")

        # Fallback: Manual HTML parsing
        result = {
            'name': '',
            'description': '',
            'price': 0.0,
            'original_price': 0.0,
            'image_url': '',
            'gallery_images': [],
            'shipping_time': '10-20 days',
            'product_id': '',
            'url': url,
            'supplier': 'AliExpress Supplier'
        }

        # Try meta tag FIRST (most reliable for AliExpress)
        meta_tag = soup.find('meta', property='og:title')
        if meta_tag and meta_tag.get('content'):
            result['name'] = meta_tag['content']
            # Clean up the name - remove " - AliExpress XXXX" suffix
            result['name'] = result['name'].split(' - AliExpress')[0].strip()
            logger.info(f"✅ Found name from meta tag: {result['name'][:60]}")

        # Fallback to HTML selectors if meta tag fails
        if not result['name']:
            name_selectors = [
                'h1[data-pl="product-title"]',
                'h1.product-title-text',
                '.product-title',
                'h1',
                '[class*="Title"]',
            ]

            for selector in name_selectors:
                name_tag = soup.select_one(selector)
                if name_tag:
                    result['name'] = name_tag.get_text(strip=True)
                    if result['name']:
                        logger.info(f"✅ Found name with selector '{selector}': {result['name'][:50]}")
                        break

        if not result['name']:
            logger.error("❌ Could not find product name with any method")
            logger.error("⚠️ This likely means AliExpress is blocking the scraper")
            return None

        # Description
        desc_selectors = ['.detail-desc', '.product-description', '[class*="description"]']
        for selector in desc_selectors:
            desc_tag = soup.select_one(selector)
            if desc_tag:
                for tag in desc_tag.select('script, style, noscript'):
                    tag.decompose()
                result['description'] = desc_tag.get_text(separator='\n', strip=True)[:1000]
                break

        if not result['description']:
            result['description'] = result['name']

        # Images - Try meta tag first (most reliable)
        meta_tag = soup.find('meta', property='og:image')
        if meta_tag and meta_tag.get('content'):
            result['image_url'] = meta_tag['content']
            logger.info(f"✅ Found image from meta tag: {result['image_url'][:60]}")

        # Fallback to HTML selectors
        if not result['image_url']:
            img_selectors = [
                'img[class*="mainPic"]',
                '.magnifier-image',
                'img[class*="ImageView"]',
                '.product-image img',
            ]

            for selector in img_selectors:
                img_tag = soup.select_one(selector)
                if img_tag and img_tag.get('src'):
                    img_url = img_tag['src']
                    if not img_url.startswith('http'):
                        img_url = 'https:' + img_url
                    result['image_url'] = img_url
                    logger.info(f"✅ Found image: {img_url[:60]}")
                    break

        # Gallery images
        gallery_imgs = soup.select('img[class*="image"]')[:6]
        for img in gallery_imgs:
            if img.get('src') and img['src'] != result['image_url']:
                img_url = img['src']
                if not img_url.startswith('http'):
                    img_url = 'https:' + img_url
                result['gallery_images'].append(img_url)

        # Also try to extract from window._d_c_.DCData.imagePathList
        try:
            script_tags = soup.find_all('script')
            for script in script_tags:
                if script.string and 'imagePathList' in script.string:
                    # Extract imagePathList array
                    match = re.search(r'"imagePathList":\s*(\[.*?\])', script.string)
                    if match:
                        import json
                        images = json.loads(match.group(1))
                        for img_url in images[:6]:
                            if img_url and img_url not in result['gallery_images'] and img_url != result['image_url']:
                                result['gallery_images'].append(img_url)
                        logger.info(f"✅ Found {len(images)} images from imagePathList")
                        break
        except Exception as e:
            logger.debug(f"Could not extract imagePathList: {e}")

        # Price
        if result['price'] == 0:
            price_selectors = [
                '[class*="price"] [class*="value"]',
                '.product-price-value',
                '[data-spm-anchor-id*="price"]',
                'meta[property="og:price:amount"]',
            ]
            for selector in price_selectors:
                if selector.startswith('meta'):
                    meta_tag = soup.find('meta', property='og:price:amount')
                    if meta_tag and meta_tag.get('content'):
                        try:
                            result['price'] = float(meta_tag['content'])
                            logger.info(f"✅ Found price from meta: ${result['price']}")
                            break
                        except:
                            pass
                else:
                    price_tag = soup.select_one(selector)
                    if price_tag:
                        try:
                            price_text = price_tag.get_text(strip=True)
                            price_match = re.search(r'[\d,]+\.?\d*', price_text)
                            if price_match:
                                result['price'] = float(price_match.group().replace(',', ''))
                                logger.info(f"✅ Found price: ${result['price']}")
                                break
                        except:
                            pass

        # If still no price, use category-based defaults
        if result['price'] == 0:
            # Set reasonable default prices based on common product categories
            category_defaults = {
                'gaming-chairs': 150.0,
                'keyboards': 50.0,
                'mice': 30.0,
                'monitors': 200.0,
                'headsets': 60.0,
            }

            # Try to guess category from URL or use generic default
            default_price = 50.0  # Generic default
            for category, price in category_defaults.items():
                if category in url.lower():
                    default_price = price
                    break

            result['price'] = default_price
            logger.warning(f"⚠️ Using default price: ${default_price}")

        result['original_price'] = result['price']

        # Extract product ID from URL
        product_id_match = re.search(r'/item/(\d+)\.html', url)
        if product_id_match:
            result['product_id'] = product_id_match.group(1)

        logger.info(f"✅ Scraping complete: {result['name'][:50]}")
        return result

    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Network error: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"❌ Scraping error: {str(e)}", exc_info=True)
        return None


def get_aliexpress_product_details(url):
    """Get product details via scraping"""
    return scrape_product_details(url)


def generate_affiliate_link(product_url):
    """Generate affiliate link with tracking"""
    if not hasattr(settings, 'ALIEXPRESS_TRACKING_ID'):
        return product_url
    return f"{product_url}?af=YOUR_AFFILIATE_ID&aff_trace_key={settings.ALIEXPRESS_TRACKING_ID}"


def import_aliexpress_product(url, category_slug):
    """
    Full product import with transaction safety and proper Supplier handling.
    """
    try:
        logger.info(f"📦 Starting import: {url}")
        product_data = get_aliexpress_product_details(url)

        if not product_data:
            error_msg = "Failed to fetch product details - AliExpress may be blocking requests"
            logger.error(f"❌ {error_msg}")
            return None, error_msg

        if not product_data.get('name'):
            error_msg = "Product name is empty - scraping failed"
            logger.error(f"❌ {error_msg}")
            return None, error_msg

        logger.info(f"✅ Product data retrieved: {product_data['name']}")

        # Create/get category
        slug = slugify(category_slug)
        category, created = Category.objects.get_or_create(
            slug=slug,
            defaults={'name': category_slug}
        )

        # Create or get Supplier instance
        supplier_name = product_data.get('supplier', 'AliExpress Supplier')
        supplier, supplier_created = Supplier.objects.get_or_create(
            name=supplier_name,
            defaults={
                'website': 'https://www.aliexpress.com',
                'notes': 'AliExpress dropshipping supplier'
            }
        )

        # Prepare product data
        short_description = product_data['description'][:200] + "..." if product_data['description'] else product_data[
            'name']

        # Create product in transaction
        with transaction.atomic():
            product = Product.objects.create(
                category=category,
                name=product_data['name'][:200],
                description=product_data['description'] or product_data['name'],
                short_description=short_description,
                price=product_data['price'],
                discount_price=product_data['original_price'] if product_data['original_price'] != product_data[
                    'price'] else None,
                stock=100,
                available=True,
                is_dropship=True,
                supplier=supplier,
                supplier_url=url,
                supplier_product_id=product_data.get('product_id', ''),
                shipping_time=product_data['shipping_time'],
                commission_rate=15.0
            )

            logger.info(f"✅ Product created: {product.name} (ID: {product.id})")

            # Download main image
            if product_data['image_url']:
                img_content, img_name = download_image(product_data['image_url'])
                if img_content and img_name:
                    product.image.save(img_name, img_content, save=True)
                    logger.info(f"✅ Main image saved")
                else:
                    logger.warning(f"⚠️ Failed to download main image")

            # Download additional images
            for idx, img_url in enumerate(product_data.get('gallery_images', [])[:5], 1):
                img_content, img_name = download_image(img_url)
                if img_content and img_name:
                    product_image = ProductImage(product=product)
                    product_image.image.save(img_name, img_content, save=False)
                    product_image.save()
                    logger.info(f"✅ Gallery image {idx} saved")

        logger.info(f"✅ Import complete: {product.name} (ID: {product.id})")
        return product, "Success"

    except Exception as e:
        logger.error(f"❌ Import failed: {str(e)}", exc_info=True)
        return None, str(e)


def fulfill_order(order_item):
    """Simulate dropshipping order fulfillment"""
    try:
        product = order_item.product
        if not product.is_dropship:
            return False, "Not a dropshipping product"

        tracking_number = f"TRACK-{uuid.uuid4().hex[:12]}"
        estimated_delivery = product.shipping_time

        if hasattr(order_item, 'tracking_number'):
            order_item.tracking_number = tracking_number
        if hasattr(order_item, 'estimated_delivery'):
            order_item.estimated_delivery = estimated_delivery
        if hasattr(order_item, 'dropship_processed'):
            order_item.dropship_processed = True
        order_item.save()

        affiliate_link = generate_affiliate_link(product.supplier_url)

        logger.info(f"SIMULATED fulfillment for order item {order_item.id}")
        logger.info(f"Product URL: {product.supplier_url}")
        logger.info(f"Affiliate link: {affiliate_link}")

        return True, f"Tracking: {tracking_number}"

    except Exception as e:
        logger.error(f"Fulfillment simulation failed: {str(e)}")
        return False, str(e)