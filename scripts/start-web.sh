#!/bin/bash
set -e

echo "=== Starting Django Web Service ==="

# Navigate to Django app directory
cd myapp

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput

# Run database migrations
echo "Running database migrations..."
python manage.py migrate --noinput

# Compile translation messages
echo "Compiling translation messages..."
python manage.py compilemessages || true

# Create cache tables if needed
echo "Creating cache tables..."
python manage.py createcachetable || true

# Start Gunicorn server
echo "Starting Gunicorn web server..."
exec gunicorn myapp.wsgi:application \
    --bind 0.0.0.0:${PORT:-8000} \
    --workers ${WEB_CONCURRENCY:-2} \
    --threads 4 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile - \
    --log-level info
