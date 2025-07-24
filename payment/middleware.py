# payment/middleware.py
from django.utils import timezone
from django.conf import settings
import pycountry
import geoip2.database
import logging
import socket
from django.core.cache import cache

logger = logging.getLogger(__name__)


class GeoLocationMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        try:
            # Use more reliable GeoIP database
            self.reader = geoip2.database.Reader(settings.GEOIP_PATH)
        except FileNotFoundError:
            logger.error("GeoIP database not found at %s", settings.GEOIP_PATH)
            self.reader = None
        except Exception as e:
            logger.exception("Error loading GeoIP database")
            self.reader = None

    def __call__(self, request):
        # Always set default values first
        request.country = settings.DEFAULT_COUNTRY
        request.currency = settings.DEFAULT_CURRENCY

        # Get real client IP considering proxies
        ip = self.get_client_ip(request)

        # Skip private IPs and localhost
        if ip and not self.is_private_ip(ip) and self.reader:
            cache_key = f'geoip_{ip}'
            geo_data = cache.get(cache_key)

            if not geo_data:
                try:
                    response = self.reader.city(ip)
                    geo_data = {
                        'country': response.country.iso_code,
                        'currency': self.get_currency_for_country(
                            response.country.iso_code
                        )
                    }
                    # Cache for 24 hours
                    cache.set(cache_key, geo_data, 86400)
                except (geoip2.errors.AddressNotFoundError, ValueError):
                    geo_data = {'country': None, 'currency': None}
                except Exception as e:
                    logger.error("GeoIP lookup error: %s", str(e))
                    geo_data = {'country': None, 'currency': None}

            if geo_data.get('country'):
                request.country = geo_data['country']
                request.currency = geo_data['currency'] or settings.DEFAULT_CURRENCY

        return self.get_response(request)

    def get_client_ip(self, request):
        """Get real client IP considering proxies"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            # The header can contain multiple IPs (proxy chain)
            ips = [ip.strip() for ip in x_forwarded_for.split(',')]
            # The client IP is usually the first one
            return ips[0]
        return request.META.get('REMOTE_ADDR')

    def is_private_ip(self, ip):
        """Check if IP is in private range"""
        try:
            addr = socket.inet_pton(socket.AF_INET, ip)
        except socket.error:
            try:
                addr = socket.inet_pton(socket.AF_INET6, ip)
            except socket.error:
                return False

        # Check IPv4 private ranges
        if len(addr) == 4:
            return any([
                ip.startswith('10.'),
                ip.startswith('192.168.'),
                ip.startswith('172.') and 16 <= int(ip.split('.')[1]) <= 31,
                ip == '127.0.0.1'
            ])

        # Check IPv6 private ranges
        return ip.startswith('fc00:') or ip.startswith('fe80:')

    def get_currency_for_country(self, country_code):
        """More robust currency mapping with fallbacks"""
        # Custom mapping for special cases
        CUSTOM_CURRENCY_MAP = {
            'XK': 'EUR',  # Kosovo
            'TW': 'TWD',  # Taiwan
            'PS': 'ILS',  # Palestine
            'CU': 'USD',  # Cuba
            'IR': 'IRR',  # Iran
        }

        if country_code in CUSTOM_CURRENCY_MAP:
            return CUSTOM_CURRENCY_MAP[country_code]

        try:
            country = pycountry.countries.get(alpha_2=country_code)
            if country:
                # Handle countries with multiple currencies
                if country_code == 'CH':
                    return 'CHF'
                elif country_code in ('US', 'EC', 'SV'):
                    return 'USD'
                elif country_code in ('AU', 'CK', 'NU', 'NF', 'TV'):
                    return 'AUD'
                # Default to first official currency
                currencies = pycountry.currencies.get(numeric=country.numeric)
                if currencies:
                    return currencies[0].alpha_3
        except Exception:
            pass

        return None