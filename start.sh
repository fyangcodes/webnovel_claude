#!/bin/bash

# Navigate to Django app directory
cd myapp

# Run Django setup commands
echo "Running collectstatic..."
python manage.py collectstatic --noinput

echo "Running migrations..."
python manage.py migrate

echo "Starting background worker..."
python manage.py process_tasks &

echo "Starting web server..."
exec gunicorn myapp.wsgi --bind 0.0.0.0:$PORT