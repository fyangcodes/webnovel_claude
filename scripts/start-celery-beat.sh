#!/bin/bash
set -e

echo "=== Starting Celery Beat Service ==="

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

# Remove old celerybeat-schedule.db if exists (prevents conflicts)
rm -f celerybeat-schedule.db celerybeat-schedule

# Start Celery beat scheduler
echo "Starting Celery beat scheduler..."
exec celery -A myapp beat \
    --loglevel=info \
    --scheduler django_celery_beat.schedulers:DatabaseScheduler
