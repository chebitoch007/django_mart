#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

echo "🚀 Starting deployment tasks..."

# 1. Apply Database Migrations
echo "📦 Applying database migrations..."
python manage.py migrate --noinput

# 2. Create Superuser (idempotent - only if not exists)
echo "👤 Creating superuser..."
python manage.py shell -c "
import os
from django.contrib.auth import get_user_model

User = get_user_model()
# Use email as the primary identifier (consistent with your models.py)
email = os.environ.get('DJANGO_SUPERUSER_EMAIL', 'admin@example.com')
username = os.environ.get('DJANGO_SUPERUSER_USERNAME', 'admin')
password = os.environ.get('DJANGO_SUPERUSER_PASSWORD')

# Check if user exists by EMAIL (your USERNAME_FIELD)
if not User.objects.filter(email=email).exists():
    if password:
        print(f'Creating superuser {email}...')
        # We MUST provide first_name and last_name because they are REQUIRED_FIELDS in your models.py
        User.objects.create_superuser(
            email=email,
            username=username,
            password=password,
            first_name='System',
            last_name='Admin'
        )
        print('Superuser created successfully.')
    else:
        print('Skipping superuser creation: DJANGO_SUPERUSER_PASSWORD not set')
else:
    print(f'Superuser {email} already exists. Skipping creation.')
"

# 3. Start Gunicorn
# Uses the PORT environment variable provided by Render
echo "⚡ Starting Gunicorn on port $PORT..."
exec gunicorn asai.wsgi_prod:application --bind 0.0.0.0:$PORT --workers 4 --threads 2