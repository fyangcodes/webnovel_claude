"""
Context processors for making data available to all templates.
"""


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
