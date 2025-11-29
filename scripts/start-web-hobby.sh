#!/bin/bash
set -e

echo "=== Starting Django Web Service (Hobby Plan - All-in-One) ==="
echo "Configuration:"
echo "  - ENABLE_CELERY: ${ENABLE_CELERY:-false}"
echo "  - ENABLE_CELERY_BEAT: ${ENABLE_CELERY_BEAT:-false}"
echo "  - WEB_CONCURRENCY: ${WEB_CONCURRENCY:-1}"
echo ""

# Navigate to Django app directory
cd myapp

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput

# Run database migrations
echo "Running database migrations..."
python manage.py migrate --noinput

# Load initial data fixtures (only if database is empty)
echo "Checking if initial data needs to be loaded..."
USER_COUNT=$(python manage.py shell -c "from accounts.models import User; print(User.objects.count())")
LANGUAGE_COUNT=$(python manage.py shell -c "from books.models import Language; print(Language.objects.count())")
SECTION_COUNT=$(python manage.py shell -c "from books.models import Section; print(Section.objects.count())")

if [ "$USER_COUNT" = "0" ]; then
    echo "Loading user fixture..."
    python manage.py loaddata ./fixtures/users.json
    echo "✅ Superuser loaded"
else
    echo "Users already exist, skipping superuser fixture load"
fi

if [ "$LANGUAGE_COUNT" = "0" ]; then
    echo "Loading language fixtures..."
    python manage.py loaddata ./fixtures/languages.json
    echo "✅ Languages loaded"
else
    echo "Languages already exist, skipping fixture load"
fi

if [ "$SECTION_COUNT" = "0" ]; then
    echo "Loading section fixtures..."
    python manage.py loaddata ./fixtures/sections.json
    echo "✅ Sections loaded"
else
    echo "Sections already exist, skipping fixture load"
fi

# Compile translation messages
echo "Compiling translation messages..."
python manage.py compilemessages || true

# Create cache tables if needed
echo "Creating cache tables..."
python manage.py createcachetable || true

# Trap signals for graceful shutdown
trap 'echo "Shutting down gracefully..."; kill -TERM $CELERY_WORKER_PID $CELERY_BEAT_PID $GUNICORN_PID 2>/dev/null; wait' SIGTERM SIGINT

# Start Celery worker in background (if enabled)
if [ "${ENABLE_CELERY}" = "true" ]; then
    echo "Starting Celery worker in background..."
    celery -A myapp worker \
        --loglevel=info \
        --concurrency=${CELERY_WORKER_CONCURRENCY:-1} \
        --max-tasks-per-child=100 \
        --time-limit=300 \
        --soft-time-limit=240 &
    CELERY_WORKER_PID=$!
    echo "Celery worker started with PID: $CELERY_WORKER_PID"

    # Start Celery beat in background (if enabled)
    if [ "${ENABLE_CELERY_BEAT}" = "true" ]; then
        echo "Starting Celery beat scheduler in background..."
        # Remove old schedule file to prevent conflicts
        rm -f celerybeat-schedule celerybeat-schedule.db
        celery -A myapp beat \
            --loglevel=info \
            --scheduler django_celery_beat.schedulers:DatabaseScheduler &
        CELERY_BEAT_PID=$!
        echo "Celery beat started with PID: $CELERY_BEAT_PID"
    fi

    # Give Celery a moment to start
    sleep 2
    echo "Celery services started successfully"
else
    echo "Celery disabled (ENABLE_CELERY not set to 'true')"
fi

# Start Gunicorn web server in foreground
echo ""
echo "Starting Gunicorn web server..."
gunicorn myapp.wsgi:application \
    --bind 0.0.0.0:${PORT:-8000} \
    --workers ${WEB_CONCURRENCY:-1} \
    --threads 2 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile - \
    --log-level info &
GUNICORN_PID=$!
echo "Gunicorn started with PID: $GUNICORN_PID"

# Wait for Gunicorn to finish (keeps script running)
wait $GUNICORN_PID
