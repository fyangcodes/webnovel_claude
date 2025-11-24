# This will make sure the app is always imported when
# Django starts so that shared_task will use this app.
try:
    from .celery import app as celery_app
    # Make it available as both 'celery_app' and 'app' for CLI
    app = celery_app
    __all__ = ('celery_app', 'app')
except ImportError:
    # Celery not installed, skip initialization
    pass
