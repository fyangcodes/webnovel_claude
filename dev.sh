#!/bin/bash

source .venv/bin/activate

# Navigate to Django app directory
cd myapp

# Run Django setup commands
echo "Running collectstatic..."
python manage.py collectstatic --noinput

echo "Making migrations..."
python manage.py makemigrations

echo "Running migrations..."
python manage.py migrate

echo "Starting background worker..."
python manage.py process_translations &

echo "Starting web server..."
python manage.py runserver
