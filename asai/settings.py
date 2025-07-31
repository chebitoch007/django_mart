"""
Django settings for asai project.
"""

import os
from pathlib import Path
import environ

# Initialize environment
env = environ.Env()

# Set BASE_DIR correctly
BASE_DIR = Path(__file__).resolve().parent.parent

# Read .env file
environ.Env.read_env(os.path.join(BASE_DIR, '.env'))

# ================== Core Production Settings ==================
SECRET_KEY = env('DJANGO_SECRET_KEY')
DEBUG = env.bool('DJANGO_DEBUG', default=False)
ALLOWED_HOSTS = env.list('DJANGO_ALLOWED_HOSTS', default=['localhost', '127.0.0.1'])
CSRF_TRUSTED_ORIGINS = env.list('CSRF_TRUSTED_ORIGINS', default=[])

handler404 = 'store.views.custom_404'
handler500 = 'store.views.custom_500'

# ================== Security Headers ==================
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_SSL_REDIRECT = env.bool('SECURE_SSL_REDIRECT', default=False)
    SESSION_COOKIE_SECURE = env.bool('SESSION_COOKIE_SECURE', default=False)

    SESSION_COOKIE_SAMESITE = 'Lax'  # Prevents redirect loops with third-party cookies

    CSRF_COOKIE_SECURE = env.bool('CSRF_COOKIE_SECURE', default=False)
    try:
        SECURE_HSTS_SECONDS = env.int('SECURE_HSTS_SECONDS', default=0)
    except ValueError:
        SECURE_HSTS_SECONDS = 31536000  # Fallback to 1 year
        print("Warning: Invalid SECURE_HSTS_SECONDS value. Using default 1 year.")
    SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool('SECURE_HSTS_INCLUDE_SUBDOMAINS', default=False)
    SECURE_HSTS_PRELOAD = env.bool('SECURE_HSTS_PRELOAD', default=False)
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_BROWSER_XSS_FILTER = True
    X_FRAME_OPTIONS = 'DENY'
    SESSION_COOKIE_HTTPONLY = True  # Prevent XSS attacks
    SESSION_EXPIRE_AT_BROWSER_CLOSE = True  # Session expires when browser closes
    SESSION_COOKIE_AGE = 1800  # 30 minutes
    CSRF_COOKIE_SECURE = True
# Payment settings
PAYMENT_SETTINGS = {
    'USE_SMS': False,
    'PAYMENT_WINDOW_HOURS': 48,
    'MOBILE_MONEY_PROVIDERS': ['MPesa', 'Airtel Money'],
    'SMS_API_KEY': env('SMS_API_KEY', default=None),
    'SITE_URL': env('SITE_URL', default='http://localhost:8000'),
}

# ================== Application Definition ==================
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    'django.contrib.postgres',
    'django_extensions',
    'crispy_forms',
    'django_countries',
    'mptt',
    'store.apps.StoreConfig',
    'cart.apps.CartConfig',
    'users.apps.UsersConfig',
    'orders.apps.OrdersConfig',
    'payment.apps.PaymentConfig',
    'core',
    'sslserver',
    'encrypted_model_fields',
    'paypal.standard.ipn',
    'easycart',
    'widget_tweaks',
    'db_cleaner',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django.middleware.cache.UpdateCacheMiddleware',
    'django.middleware.cache.FetchFromCacheMiddleware',
]


# ================== Templates & URLs ==================
ROOT_URLCONF = 'asai.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'cart.context_processors.cart',
                'store.context_processors.currency_context',
                'store.context_processors.top_level_categories',
            ],
            'loaders': [
                ('django.template.loaders.cached.Loader', [
                    'django.template.loaders.filesystem.Loader',
                    'django.template.loaders.app_directories.Loader',
                ]),
            ],
        },
    },
]

#Session engine
SESSION_ENGINE = "django.contrib.sessions.backends.cached_db"

# ================== Database ==================
DATABASES = {
    'default': env.db('DATABASE_URL')
}

# ================== Password Validation ==================
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator','OPTIONS': {'min_length': 10,}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',},
]

CURRENT_POLICY_VERSION=1.0

# ================== Internationalization ==================
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Nairobi'
USE_I18N = True
USE_TZ = True

# ================== Static & Media Files ==================
STATICFILES_DIRS = [BASE_DIR / 'store/static',BASE_DIR / 'static',]



STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
#STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Media files (Cloudflare R2)
if env('USE_CLOUDFLARE_R2', default=False):
    DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
    AWS_ACCESS_KEY_ID = env('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = env('AWS_SECRET_ACCESS_KEY')
    AWS_STORAGE_BUCKET_NAME = env('AWS_STORAGE_BUCKET_NAME')
    AWS_S3_ENDPOINT_URL = env('AWS_S3_ENDPOINT_URL')
    AWS_S3_CUSTOM_DOMAIN = env('AWS_S3_CUSTOM_DOMAIN', default=None)
    AWS_DEFAULT_ACL = 'public-read'
    AWS_QUERYSTRING_AUTH = False
else:
    MEDIA_URL = '/media/'
    MEDIA_ROOT = os.path.join(BASE_DIR, 'media')


DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ================== Security Policies ==================
PASSWORD_POLICY = {
    'min_length': 8,
    'require_uppercase': True,
    'require_lowercase': True,
    'require_numbers': True,
    'require_special_chars': True,
    'special_chars': "!@#$%^&*()_+-=[]{};':,./<>?",
}


AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',  # Primary backend
    'users.auth.EmailBackend',                   # Secondary backend
]


# ================== Custom User Model ==================
AUTH_USER_MODEL = 'users.CustomUser'

# Use email as the primary identifier
USERNAME_FIELD = 'email'
REQUIRED_FIELDS = ['first_name', 'last_name']  # Fields required when creating a superuser

# ================== Authentication URLs ==================
LOGIN_URL = '/accounts/login/'
#LOGIN_REDIRECT_URL = '/account/'
LOGIN_REDIRECT_URL = 'store:product_list'  # Ensure this points to the account view
LOGOUT_REDIRECT_URL = 'users:logout_success'

CACHE_MIDDLEWARE_ALIAS = 'default'
CACHE_MIDDLEWARE_SECONDS = 0
CACHE_MIDDLEWARE_KEY_PREFIX = ''

# ================== Third-Party Config ==================
CRISPY_TEMPLATE_PACK = 'bootstrap4'
CART_SESSION_ID = 'cart'

# ================== Payment Settings ==================
# M-Pesa Configuration
MPESA_CONSUMER_KEY = env('MPESA_CONSUMER_KEY')
MPESA_CONSUMER_SECRET = env('MPESA_CONSUMER_SECRET')
MPESA_SHORTCODE = env('MPESA_SHORTCODE')
MPESA_PASSKEY = env('MPESA_PASSKEY')
MPESA_CALLBACK_URL = env('MPESA_CALLBACK_URL')

# Airtel Money Configuration
AIRTEL_CLIENT_ID = env('AIRTEL_CLIENT_ID')
AIRTEL_CLIENT_SECRET = env('AIRTEL_CLIENT_SECRET')
AIRTEL_COUNTRY_CODE = env('AIRTEL_COUNTRY_CODE', default='KE')
AIRTEL_AUTH_URL = env('AIRTEL_AUTH_URL')
AIRTEL_PAYMENT_URL = env('AIRTEL_PAYMENT_URL')
AIRTEL_BASE_URL = env('AIRTEL_BASE_URL')
AIRTEL_SIGNATURE_KEY = env('AIRTEL_SIGNATURE_KEY')

# Stripe Configuration
STRIPE_PUBLIC_KEY = env('STRIPE_PUBLIC_KEY')
STRIPE_SECRET_KEY = env('STRIPE_SECRET_KEY')
STRIPE_WEBHOOK_SECRET = env('STRIPE_WEBHOOK_SECRET')

# PayPal Configuration
PAYPAL_CLIENT_ID = env('PAYPAL_CLIENT_ID')
PAYPAL_SECRET = env('PAYPAL_SECRET')
PAYPAL_WEBHOOK_ID = env('PAYPAL_WEBHOOK_ID')

# Currency Settings
CURRENCIES = (
    ('USD', 'US Dollar'),
    ('EUR', 'Euro'),
    ('GBP', 'British Pound'),
    ('KES', 'Kenyan Shilling'),
    ('UGX', 'Ugandan Shilling'),
    ('TZS', 'Tanzanian Shilling'),
)

CURRENCY_SYMBOLS = {
    'USD': '$',
    'EUR': '€',
    'GBP': '£',
    'KES': 'KSh',
    'UGX': 'USh',
    'TZS': 'TSh'
}
DEFAULT_CURRENCY = env('DEFAULT_CURRENCY', default='KES')

# Encryption settings
FIELD_ENCRYPTION_KEY = env.str(
    'FIELD_ENCRYPTION_KEY',
    default='django-insecure-+key'  # Default for development only
)

# Add rotation mechanism for encryption key
#FIELD_ENCRYPTION_KEY = os.environ.get('FIELD_ENCRYPTION_KEY')
#FIELD_ENCRYPTION_KEY_PREVIOUS = os.environ.get('FIELD_ENCRYPTION_KEY_PREVIOUS', default=None)

# Transaction Timeouts
PAYMENT_TIMEOUT = env.int('PAYMENT_TIMEOUT', default=300)

# Fraud prevention
FRAUD_PREVENTION = {
    'GEO_LIMIT': env.list('ALLOWED_COUNTRIES', default=['KE', 'TZ', 'UG']),
    'IP_WHITELIST': env.list('TRUSTED_IPS', default=[]),
}

# Currency Formatting
CURRENCY_FORMATS = {
    'KES': {'format': 'KSh{amount:.2f}', 'decimal_places': 2},
    'UGX': {'format': 'UGX{amount:.0f}', 'decimal_places': 0},
    'TZS': {'format': 'TSh{amount:.0f}', 'decimal_places': 0},
    'USD': {'format': '${amount:.2f}', 'decimal_places': 2},
    'EUR': {'format': '€{amount:.2f}', 'decimal_places': 2},
}

# Order settings
ORDER_EXPIRY_DAYS = env.int('ORDER_EXPIRY_DAYS', default=3)

# Email configuration
EMAIL_BACKEND = env('EMAIL_BACKEND', default='django.core.mail.backends.console.EmailBackend')
if EMAIL_BACKEND == 'django.core.mail.backends.smtp.EmailBackend':
    EMAIL_HOST = env('EMAIL_HOST')
    EMAIL_PORT = env.int('EMAIL_PORT', default=587)
    EMAIL_USE_TLS = env.bool('EMAIL_USE_TLS', default=True)
    EMAIL_HOST_USER = env('EMAIL_HOST_USER')
    EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD')
    DEFAULT_FROM_EMAIL = env('DEFAULT_FROM_EMAIL', default='noreply@yourdomain.com')

# ================== Logging Configuration ==================
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,

    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },

    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': os.path.join(BASE_DIR, 'logs', 'django.log'),
            'formatter': 'verbose',
        },
        'payment_file': {
            'level': 'DEBUG',
            'class': 'logging.FileHandler',
            'filename': os.path.join(BASE_DIR, 'logs', 'payments.log'),
            'formatter': 'verbose',
        },
    },

    'root': {
        'handlers': ['console'],
        'level': 'DEBUG',
    },

    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': True,
        },
        'payment': {
            'handlers': ['payment_file', 'console'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'orders': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG',
            'propagate': True,
        },
        'core': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG',
            'propagate': True,
        },
    },
}

# reCAPTCHA Configuration
RECAPTCHA_SITE_KEY = env('RECAPTCHA_SITE_KEY')
RECAPTCHA_SECRET_KEY = env('RECAPTCHA_SECRET_KEY')

'''# ================== Content Security Policy ==================
# Development-friendly settings (safe for local work)
CSP_ENABLED = False  # Disable CSP in development
CSP_IGNORE_MIGRATION_CHECK = True  # Bypass migration checks
SILENCED_SYSTEM_CHECKS = ['csp.E001']  # Disable CSP system checks"""

CSP_EXCLUDE_TEMPLATE_TAGS = True
# ================== PRODUCTION-READY CSP CONFIG (UNCOMMENT WHEN DEPLOYING) ==================
# Remove the development settings above and uncomment this section for production

if DEBUG:
    CSP_ENABLED = False  # Disable CSP in development
    CSP_IGNORE_MIGRATION_CHECK = True  # Bypass migration checks
    SILENCED_SYSTEM_CHECKS = ['csp.E001']  # Disable CSP system checks
else:
    # Production CSP settings (copied from above)
    CSP_ENABLED = True

# Strict CSP directives for production
CSP_DEFAULT_SRC = ["'self'"]
CSP_SCRIPT_SRC = [
    "'self'",
    "https://js.stripe.com",
    "https://www.paypal.com",
    "https://unpkg.com"
]
CSP_STYLE_SRC = [
    "'self'",
    "https://fonts.googleapis.com",
    "https://cdnjs.cloudflare.com",
    "https://cdn.jsdelivr.net"
]
CSP_IMG_SRC = [
    "'self'",
    "data:",
    "https://*.stripe.com",
    "https://www.paypal.com",
    "https://cdnjs.cloudflare.com"
]
CSP_FONT_SRC = [
    "'self'",
    "https://fonts.gstatic.com",
    "https://cdnjs.cloudflare.com"
]
CSP_FRAME_SRC = [
    "'self'",
    "https://js.stripe.com",
    "https://www.paypal.com"
]
CSP_CONNECT_SRC = [
    "'self'",
    "https://api.stripe.com",
    "https://api.paypal.com",
    "https://fonts.googleapis.com",
    "https://fonts.gstatic.com"
]
CSP_OBJECT_SRC = ["'none'"]
CSP_BASE_URI = ["'self'"]
CSP_FORM_ACTION = ["'self'"]

# Security hardening (production only)
CSP_INCLUDE_NONCE_IN = ['script-src', 'style-src']  # Require nonces for inline code
CSP_BLOCK_ALL_MIXED_CONTENT = True
CSP_UPGRADE_INSECURE_REQUESTS = True
CSP_REPORT_ONLY = False  # Enforce policy (not just report)

# ================== END PRODUCTION CSP CONFIG ==================
'''
'''# AliExpress Affiliate
ALIEXPRESS_API_KEY = env('ALIEXPRESS_API_KEY', default='')
ALIEXPRESS_API_SECRET = env('ALIEXPRESS_API_SECRET', default='')
ALIEXPRESS_AFFILIATE_BASE_URL = 'https://s.click.aliexpress.com/deep_link.htm'

ALIEXPRESS_TRACKING_ID = "YOUR_UNIQUE_TRACKING_ID"  # For affiliate links"""'''

ALIEXPRESS_API_NAME = "aliexpress-datahub"  # The API you chose
ALIEXPRESS_API_KEY = "f239611ffamsh38ffe813082ee63p1186d8jsnad44ba7c8464"  # Your RapidAPI key
ALIEXPRESS_API_HOST = "aliexpress-datahub.p.rapidapi.com"  # API host



# Product Import Settings
MAX_IMPORT_IMAGES = 5
IMPORT_DEFAULT_STOCK = 100
IMPORT_DEFAULT_COMMISSION = 15.0

# PCI DSS Compliance Settings
PCI_COMPLIANCE = {
    'CVV_STORAGE': False,  # Never store CVV
    'CARD_DATA_ENCRYPTION': True,
    'TOKENIZATION': True,  # Use payment gateway tokens
    'AUDIT_LOG_RETENTION': 365,  # Days to keep audit logs
}

EXCHANGERATE_API_KEY = env('EXCHANGERATE_API_KEY', default=None)



# Media files (use S3)
DEFAULT_FILE_STORAGE = "storages.backends.s3boto3.S3Boto3Storage"
AWS_ACCESS_KEY_ID = os.getenv('AWS_KEY')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET')
AWS_STORAGE_BUCKET_NAME = "your-bucket"
AWS_S3_REGION_NAME = "eu-central-1"  # Change to your region

# Cache configuration
if DEBUG:
    # Use local memory cache during development
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'asai-cache',
        }
    }
else:
    # Use Redis in production
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': env('REDIS_URL', default='redis://127.0.0.1:6379/1'),
            'TIMEOUT': 60 * 60 * 4,  # 4 hours
            'OPTIONS': {
                'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            }
        }
    }

    # Currency caching settings
CURRENCY_CACHE_TIMEOUT = 60 * 60 * 4  # 4 hours
CURRENCY_CACHE_TIMEOUT_ERROR = 60 * 5  # 5 minutes for errors
