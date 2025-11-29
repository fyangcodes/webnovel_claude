#!/bin/bash
set -e

echo "=== Starting Celery Worker Service ==="

# Navigate to Django app directory
cd myapp

# Wait for database to be ready
echo "Waiting for database to be ready..."
python -c "
import time
import sys
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myapp.settings')
django.setup()

from django.db import connection
from django.db.utils import OperationalError

max_retries = 30
retry_interval = 2

for i in range(max_retries):
    try:
        connection.ensure_connection()
        print('Database is ready!')
        sys.exit(0)
    except OperationalError:
        print(f'Database not ready, retrying ({i+1}/{max_retries})...')
        time.sleep(retry_interval)

print('Database connection failed after retries')
sys.exit(1)
"

# Start Celery worker
echo "Starting Celery worker..."
exec celery -A myapp worker \
    --loglevel=info \
    --concurrency=${CELERY_WORKER_CONCURRENCY:-2} \
    --max-tasks-per-child=100 \
    --time-limit=300 \
    --soft-time-limit=240
