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
    # Aggregate stats from Redis to PostgreSQL every 5 minutes (for development)
    'aggregate-stats-frequent': {
        'task': 'books.tasks.analytics.aggregate_stats_hourly',
        'schedule': crontab(minute='*/5'),  # Every 5 minutes
    },
    # Update unique view counts daily
    'update-time-period-uniques': {
        'task': 'books.tasks.analytics.update_time_period_uniques',
        'schedule': crontab(hour=2, minute=0),  # Daily at 2:00 AM
    },
    # Clean up old view events daily
    'cleanup-old-events': {
        'task': 'books.tasks.analytics.cleanup_old_view_events',
        'schedule': crontab(hour=3, minute=0),  # Daily at 3:00 AM
    },
    # Calculate trending scores every 6 hours
    'calculate-trending': {
        'task': 'books.tasks.analytics.calculate_trending_scores',
        'schedule': crontab(minute=0, hour='*/6'),  # Every 6 hours
    },
    # Process pending translation jobs every 2 minutes
    'process-translation-jobs': {
        'task': 'books.tasks.chapter_translation.process_translation_jobs',
        'schedule': crontab(minute='*/2'),  # Every 2 minutes
    },
    # Process pending analysis jobs every 2 minutes
    'process-analysis-jobs': {
        'task': 'books.tasks.chapter_analysis.process_analysis_jobs',
        'schedule': crontab(minute='*/2'),  # Every 2 minutes
    },
}

# Configure Celery timezone
app.conf.timezone = 'UTC'


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Debug task for testing Celery setup"""
    print(f'Request: {self.request!r}')
