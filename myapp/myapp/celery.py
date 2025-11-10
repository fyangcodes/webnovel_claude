"""
Celery configuration for webnovel translation app.
"""

import os
from celery import Celery
from celery.schedules import crontab

# Set the default Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myapp.settings')

# Create Celery app
app = Celery('myapp')

# Load configuration from Django settings with CELERY namespace
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks in all installed apps
app.autodiscover_tasks()

# Configure Celery Beat schedule
app.conf.beat_schedule = {
    # Aggregate stats from Redis to PostgreSQL every hour
    'aggregate-stats-hourly': {
        'task': 'books.tasks.aggregate_stats_hourly',
        'schedule': crontab(minute=0),  # Every hour at :00
    },
    # Update unique view counts daily
    'update-time-period-uniques': {
        'task': 'books.tasks.update_time_period_uniques',
        'schedule': crontab(hour=2, minute=0),  # Daily at 2:00 AM
    },
    # Clean up old view events daily
    'cleanup-old-events': {
        'task': 'books.tasks.cleanup_old_view_events',
        'schedule': crontab(hour=3, minute=0),  # Daily at 3:00 AM
    },
    # Calculate trending scores every 6 hours
    'calculate-trending': {
        'task': 'books.tasks.calculate_trending_scores',
        'schedule': crontab(minute=0, hour='*/6'),  # Every 6 hours
    },
}

# Configure Celery timezone
app.conf.timezone = 'UTC'


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Debug task for testing Celery setup"""
    print(f'Request: {self.request!r}')
