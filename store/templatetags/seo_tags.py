# store/templatetags/seo_tags.py - COMPLETE FILE

from django import template
from django.utils.safestring import mark_safe
import json
import logging

register = template.Library()
logger = logging.getLogger(__name__)


@register.simple_tag
def product_structured_data(product):
    """
    Generate JSON-LD structured data for a product.
    This improves SEO by helping search engines understand the product.

    Usage in template:
    {% load seo_tags %}
    {% product_structured_data product %}
    """
    try:
        data = product.get_structured_data()
        json_data = json.dumps(data, indent=2)

        return mark_safe(
            f'<script type="application/ld+json">\n{json_data}\n</script>'
        )
    except Exception as e:
        logger.error(f"Error generating structured data: {e}")
        return ''


@register.simple_tag
def product_meta_tags(product):
    """
    Generate meta tags for product SEO.

    Usage in template:
    {% load seo_tags %}
    {% product_meta_tags product %}
    """
    try:
        from django.utils.html import escape

        meta_tags = []

        # Basic meta tags
        meta_desc = escape(product.get_meta_description())
        meta_tags.append(f'<meta name="description" content="{meta_desc}">')

        # Keywords
        if product.seo_keywords:
            keywords = escape(product.seo_keywords)
            meta_tags.append(f'<meta name="keywords" content="{keywords}">')

        # Open Graph tags for social media
        og_title = escape(product.get_meta_title())
        meta_tags.append(f'<meta property="og:title" content="{og_title}">')
        meta_tags.append(f'<meta property="og:description" content="{meta_desc}">')
        meta_tags.append(f'<meta property="og:image" content="{product.get_image_url()}">')
        meta_tags.append(f'<meta property="og:type" content="product">')

        # Twitter Card tags
        meta_tags.append('<meta name="twitter:card" content="summary_large_image">')
        meta_tags.append(f'<meta name="twitter:title" content="{og_title}">')
        meta_tags.append(f'<meta name="twitter:description" content="{meta_desc}">')
        meta_tags.append(f'<meta name="twitter:image" content="{product.get_image_url()}">')

        # Product-specific meta tags
        if product.price:
            meta_tags.append(f'<meta property="product:price:amount" content="{product.get_display_price().amount}">')
            meta_tags.append(
                f'<meta property="product:price:currency" content="{product.get_display_price().currency}">')

        if product.brand:
            brand_name = escape(product.brand.name)
            meta_tags.append(f'<meta property="product:brand" content="{brand_name}">')

        if product.stock > 0:
            meta_tags.append('<meta property="product:availability" content="in stock">')
        else:
            meta_tags.append('<meta property="product:availability" content="out of stock">')

        return mark_safe('\n'.join(meta_tags))
    except Exception as e:
        logger.error(f"Error generating meta tags: {e}")
        return ''



@register.filter
def format_keywords(keywords_text):
    """
    Format SEO keywords into badge HTML.

    Usage in template:
    {{ product.seo_keywords|format_keywords }}
    """
    if not keywords_text:
        return ''

    keywords = [k.strip() for k in keywords_text.split(',') if k.strip()]

    if not keywords:
        return ''

    from django.utils.html import escape

    html = '<div class="keyword-badges">'
    for keyword in keywords:
        escaped_keyword = escape(keyword)
        html += f'<span class="keyword-badge">{escaped_keyword}</span>'
    html += '</div>'

    return mark_safe(html)


@register.simple_tag
def breadcrumb_schema(product):
    """
    Generate breadcrumb structured data for SEO.

    Usage in template:
    {% breadcrumb_schema product %}
    """
    try:
        from django.urls import reverse

        breadcrumbs = {
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "itemListElement": [
                {
                    "@type": "ListItem",
                    "position": 1,
                    "name": "Home",
                    "item": "/"
                }
            ]
        }

        # Add category if exists
        if product.category:
            breadcrumbs["itemListElement"].append({
                "@type": "ListItem",
                "position": 2,
                "name": product.category.name,
                "item": product.category.get_absolute_url()
            })

            breadcrumbs["itemListElement"].append({
                "@type": "ListItem",
                "position": 3,
                "name": product.name,
                "item": product.get_absolute_url()
            })
        else:
            breadcrumbs["itemListElement"].append({
                "@type": "ListItem",
                "position": 2,
                "name": product.name,
                "item": product.get_absolute_url()
            })

        json_data = json.dumps(breadcrumbs, indent=2)
        return mark_safe(
            f'<script type="application/ld+json">\n{json_data}\n</script>'
        )
    except Exception as e:
        logger.error(f"Error generating breadcrumb schema: {e}")
        return ''


@register.filter
def split_features(features_text, limit=None):
    """
    Split features text into a list of features.
    Optionally limit the number of features returned.

    Usage in template:
    {% for feature in product.features|split_features:3 %}
        {{ feature }}
    {% endfor %}
    """
    if not features_text:
        return []

    features = []
    for line in features_text.split('\n'):
        line = line.strip()
        if not line:
            continue

        # Remove bullet points
        line = line.lstrip('•–—-*·➤►▪▫⦿○●').strip()

        # Remove numbering
        import re
        line = re.sub(r'^\d+[\.\)]\s*', '', line)

        if line:
            features.append(line)

            if limit and len(features) >= limit:
                break

    return features


@register.filter
def first_feature(features_text):
    """
    Get the first feature from features text.

    Usage in template:
    {{ product.features|first_feature }}
    """
    features = split_features(features_text, limit=1)
    return features[0] if features else ''


@register.simple_tag
def generate_meta_title(product, site_name="ASAI Store"):
    """
    Generate a complete meta title with site branding.

    Usage in template:
    {% generate_meta_title product "My Store" %}
    """
    title = product.get_meta_title()
    return f"{title} | {site_name}"


@register.simple_tag
def product_price_schema(product):
    """
    Generate price-specific structured data.
    Useful for product listings and search results.

    Usage in template:
    {% product_price_schema product %}
    """
    try:
        price_data = {
            "@type": "Offer",
            "price": str(product.get_display_price().amount),
            "priceCurrency": str(product.get_display_price().currency),
            "availability": "https://schema.org/InStock" if product.stock > 0 else "https://schema.org/OutOfStock",
            "url": product.get_absolute_url(),
            "seller": {
                "@type": "Organization",
                "name": "ASAI Store"
            }
        }

        # Add valid until date (30 days from now)
        from datetime import datetime, timedelta
        valid_until = (datetime.now() + timedelta(days=30)).isoformat()
        price_data["priceValidUntil"] = valid_until

        json_data = json.dumps(price_data, indent=2)
        return mark_safe(
            f'<script type="application/ld+json">\n{json_data}\n</script>'
        )
    except Exception as e:
        logger.error(f"Error generating price schema: {e}")
        return ''