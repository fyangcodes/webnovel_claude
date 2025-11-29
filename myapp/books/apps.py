from django.apps import AppConfig


class BooksConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'books'

    def ready(self):
        """
        Import signal handlers when the app is ready.
        This ensures cache invalidation signals are registered.
        Also registers system checks for production safety.
        """
        import books.signals  # noqa: F401
        import myapp.checks  # noqa: F401  # Register production safety checks
