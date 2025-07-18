import os
from django.core.wsgi import get_wsgi_application

# Set production settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'asai.settings')

# Initialize application
application = get_wsgi_application()