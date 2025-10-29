#!/bin/bash

source .venv/bin/activate

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
python manage.py runserver

# npm run build:css
# npm run watch:css
# npm run build:css:min