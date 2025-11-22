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
RUN DJANGO_SECRET_KEY=build-only-dummy-key python manage.py collectstatic --noinput

# Run application
CMD ["gunicorn", "asai.wsgi_prod:application", "--bind", "0.0.0.0:8000", "--workers", "4", "--threads", "2"]