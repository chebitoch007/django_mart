# Use Python 3.11 slim image with Bullseye
FROM python:3.11-slim-bullseye

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=on \
    PYTHONFAULTHANDLER=1 \
    PYTHONHASHSEED=random

# Install system dependencies with cleanup in single layer
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Collect static files
# FIX: We export a dummy secret key just for this command so settings.py doesn't crash
RUN DJANGO_SECRET_KEY=build-only-dummy-key \
    DATABASE_URL=sqlite:///dummy.db \
    MPESA_CONSUMER_KEY=dummy \
    MPESA_CONSUMER_SECRET=dummy \
    MPESA_SHORTCODE=dummy \
    MPESA_PASSKEY=dummy \
    MPESA_CALLBACK_URL=dummy \
    PAYPAL_CLIENT_ID=dummy \
    PAYPAL_SECRET=dummy \
    PAYPAL_WEBHOOK_ID=dummy \
    PAYPAL_RECEIVER_EMAIL=dummy \
    PAYSTACK_PUBLIC_KEY=dummy \
    PAYSTACK_SECRET_KEY=dummy \
    AWS_ACCESS_KEY_ID=dummy \
    AWS_SECRET_ACCESS_KEY=dummy \
    AWS_STORAGE_BUCKET_NAME=dummy \
    AWS_S3_ENDPOINT_URL=dummy \
    RECAPTCHA_SITE_KEY=dummy \
    RECAPTCHA_SECRET_KEY=dummy \
    python manage.py collectstatic --noinput

# Run application
CMD ["gunicorn", "asai.wsgi_prod:application", "--bind", "0.0.0.0:8000", "--workers", "4", "--threads", "2"]