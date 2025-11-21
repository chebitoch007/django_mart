#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

echo "🚀 Starting deployment tasks..."

# 1. Apply Database Migrations
echo "📦 Applying database migrations..."
python manage.py migrate --noinput

# 2. Create Superuser (idempotent - only if not exists)
echo "bw Creating superuser..."
python manage.py shell -c "
import os
from django.contrib.auth import get_user_model

User = get_user_model()
username = os.environ.get('DJANGO_SUPERUSER_USERNAME', 'admin')
email = os.environ.get('DJANGO_SUPERUSER_EMAIL', 'admin@example.com')
password = os.environ.get('DJANGO_SUPERUSER_PASSWORD')

if not User.objects.filter(username=username).exists():
    if password:
        print(f'Creating superuser {username}...')
        User.objects.create_superuser(username=username, email=email, password=password)
    else:
        print('Skipping superuser creation: DJANGO_SUPERUSER_PASSWORD not set')
else:
    print('Superuser already exists')
"

# 3. Start Gunicorn
echo "⚡ Starting Gunicorn..."
exec gunicorn asai.wsgi_prod:application --bind 0.0.0.0:$PORT --workers 4 --threads 2