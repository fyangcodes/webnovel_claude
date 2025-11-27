def breadcrumb_context(request):
    """
    Context processor to provide default values for breadcrumb variables
    to prevent VariableDoesNotExist errors in templates.

    All breadcrumb-related variables default to None and can be overridden
    by view contexts as needed.
    """
    return {
        "bookmaster": None,
        "book": None,
        "chaptermaster": None,
        "chapter": None,
    }


def stats_context(request):
    """
    Make view_event_id available in all templates for stats tracking.

    Views that need JavaScript tracking (like ChapterDetailView) should set
    request.view_event_id directly in get_context_data(). This context processor
    ensures it's available in templates even if set by middleware fallback.

    Note: Most views set view_event_id directly in context, but this processor
    provides a consistent way to access it across all templates.
    """
    return {
        'view_event_id': getattr(request, 'view_event_id', None),
    }


def analytics_context(request):
    """
    Make Google Analytics measurement ID available in templates.

    The GA4_MEASUREMENT_ID is configured in settings.py from the environment variable.
    If not set, analytics will not be loaded in templates.
    """
    from django.conf import settings

    return {
        'GA4_MEASUREMENT_ID': settings.GA4_MEASUREMENT_ID,
    }
