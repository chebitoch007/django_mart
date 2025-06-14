"""
Django settings for djangomart project.
"""

import os
from pathlib import Path
from pickle import NONE, FALSE

import environ
from debug_toolbar.panels import templates
from pycparser.c_ast import Default

# Initialize environment
env = environ.Env()

# Set BASE_DIR correctly
BASE_DIR = Path(__file__).resolve().parent.parent

# Read .env file
environ.Env.read_env(os.path.join(BASE_DIR, '.env'))


# ================== Core Production Settings ==================
SECRET_KEY = env('DJANGO_SECRET_KEY')
DEBUG = env.bool('DJANGO_DEBUG', default=True)
ALLOWED_HOSTS = env.list('DJANGO_ALLOWED_HOSTS')

# ================== Security Headers ==================
#SECURE_PROXY_SSL_HEADER = None
SECURE_SSL_REDIRECT = False  # Redirect HTTP → HTTPS
SESSION_COOKIE_SECURE = False  # Cookies only over HTTPS
CSRF_COOKIE_SECURE = False  # Protect form submissions
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = 'SAMEORIGIN'
SESSION_COOKIE_HTTPONLY = False  # Prevent XSS attacks

PAYMENT_SETTINGS = {
    'USE_SMS': False,
    'PAYMENT_WINDOW_HOURS': 48,
    'MOBILE_MONEY_PROVIDERS': ['MPesa', 'Airtel Money'],
  #  'SMS_API_KEY': env('SMS_API_KEY', default=None),
    'SMS_API_KEY': None,  # Set to actual key when ready
    'SITE_URL': 'http://localhost:8000'
    #'SMS_SENDER_ID': 'DJANGOMART'

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
    'django_extensions',
    'crispy_forms',
    'django_countries',
    'store.apps.StoreConfig',
    'cart.apps.CartConfig',
    'users.apps.UsersConfig',
    'orders.apps.OrdersConfig',
    'payment.apps.PaymentConfig',
    'sslserver',
    'csp',
]

# Security-related middleware
SECURITY_MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'csp.middleware.CSPMiddleware',  # Content Security Policy
]

# Core Django middleware
DJANGO_CORE_MIDDLEWARE = [
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
]



# Combined middleware setting
MIDDLEWARE = SECURITY_MIDDLEWARE + DJANGO_CORE_MIDDLEWARE



# ================== Templates & URLs ==================
ROOT_URLCONF = 'djangomart.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'cart.context_processors.cart',
                'store.context_processors.currency_context',
            ],
            'builtins': ['django.templatetags.static'],
        },
    },
]

# ================== Database ==================
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': env('DB_NAME'),
        'USER': env('DB_USER'),
        'PASSWORD': env('DB_PASSWORD'),
        'HOST': env('DB_HOST'),
        'PORT': env('DB_PORT'),
        'OPTIONS': {
            'options': '-c search_path=public'
        }
    }
}

# ================== Remaining Configuration ==================
# (Keep all other sections exactly as they were, except remove debug prints)

# Password validation, internationalization, static files,
# custom user model, and payment settings remain identical to original


# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator','OPTIONS': {'min_length': 9,}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',},
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Nairobi'
USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

PASSWORD_POLICY = {
    'min_length': 8,
    'require_uppercase': True,
    'require_lowercase': True,
    'require_numbers': True,
    'require_special_chars': True,
    'special_chars': "!@#$%^&*()_+-=[]{};':,./<>?",
    'version': '1.0',
    'requirements': [
        'At least 8 characters',
        'Mix of uppercase and lowercase letters',
        'At least one number',
        'At least one special character'
    ]
}

# Custom user model
AUTH_USER_MODEL = 'users.CustomUser'

# Login redirects
LOGIN_URL = 'users:login'
LOGIN_REDIRECT_URL = 'users:profile'
LOGOUT_REDIRECT_URL = 'home'

# Crispy forms
CRISPY_TEMPLATE_PACK = 'bootstrap4'

# Cart settings
CART_SESSION_ID = 'cart'

# ================== Payment Settings ==================
# M-Pesa Configuration
MPESA_CONSUMER_KEY = env('MPESA_CONSUMER_KEY')
MPESA_CONSUMER_SECRET = env('MPESA_CONSUMER_SECRET')
MPESA_SHORTCODE = env('MPESA_SHORTCODE', default='174379')  # Fixed this line
MPESA_PASSKEY = env('MPESA_PASSKEY')
MPESA_CALLBACK_URL = env('MPESA_CALLBACK_URL', default='http://localhost:8000/payment/mpesa-callback/')
MPESA_AUTH_URL = 'https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials'
MPESA_STK_URL = 'https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest'


# Airtel Money Configuration
AIRTEL_CLIENT_ID = env('AIRTEL_CLIENT_ID')
AIRTEL_CLIENT_SECRET = env('AIRTEL_CLIENT_SECRET')
AIRTEL_COUNTRY_CODE = env('AIRTEL_COUNTRY_CODE', default='KE')
AIRTEL_AUTH_URL = env('AIRTEL_AUTH_URL', default='https://openapi.airtel.africa/auth/oauth2/token')
AIRTEL_PAYMENT_URL = env('AIRTEL_PAYMENT_URL', default='https://openapi.airtel.africa/merchant/v1/payments/')
AIRTEL_BASE_URL = env('AIRTEL_BASE_URL', default='https://openapi.airtel.africa')

# Airtel Configuration
AIRTEL_SIGNATURE_KEY = env('AIRTEL_SIGNATURE_KEY')
AIRTEL_EXAMPLE_NUMBER = env('AIRTEL_EXAMPLE_NUMBER', default='254705123456')

# Currency Settings
DEFAULT_CURRENCY = 'KES'
CURRENCIES = {
    'KES': 'Kenyan Shilling',
    'UGX': 'Ugandan Shilling',
    'TZS': 'Tanzanian Shilling'
}

# Add these to settings.py
# Transaction Timeouts
PAYMENT_TIMEOUT = env.int('PAYMENT_TIMEOUT', default=300)


# Add fraud detection
FRAUD_PREVENTION = {
    'GEO_LIMIT': env.list('ALLOWED_COUNTRIES', default=['KE', 'TZ', 'UG']),
    'IP_WHITELIST': env.list('TRUSTED_IPS', default=[]),
}

# Currency Formatting (enhancement)
CURRENCY_FORMATS = {
    'KES': {'format': 'KSh{amount:.2f}', 'decimal_places': 2},
    'UGX': {'format': 'UGX{amount:.0f}', 'decimal_places': 0},
    'TZS': {'format': 'TSh{amount:.0f}', 'decimal_places': 0},
}

ORDER_EXPIRY_DAYS = 3  # Orders expire after 3 days
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend' # For development
DEFAULT_FROM_EMAIL = 'eliphazchebitoch@gmail.com'
#EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'  # smtp for production
EMAIL_HOST = 'your-smtp-host'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'eliphazchebitoch@gmail.com'
EMAIL_HOST_PASSWORD = 'your-email-password'
#DEFAULT_FROM_EMAIL = 'newsletter@djangomart.com'

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'DEBUG',
            'class': 'logging.FileHandler',
            'filename': 'debug.log',
            'formatter': 'verbose'
        },
    },
    'loggers': {
        'newsletter': {
            'handlers': ['file'],
            'level': 'DEBUG',
            'propagate': True,
        },
    },
}

RECAPTCHA_SITE_KEY = os.getenv('RECAPTCHA_SITE_KEY', 'dev_test_key')
RECAPTCHA_SECRET_KEY = os.getenv('RECAPTCHA_SECRET_KEY', 'dev_test_secret')





