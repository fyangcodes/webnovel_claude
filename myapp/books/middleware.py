"""
Middleware for automatic stats tracking.
Detects chapter/book views and tracks them via StatsService.
"""

from .stats import StatsService
import logging

logger = logging.getLogger(__name__)


class StatsTrackingMiddleware:
    """
    Middleware to automatically track chapter and book views.
    Views can mark content for tracking by setting request attributes.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Process the request
        response = self.get_response(request)

        # After view executes, check if stats should be tracked
        # NOTE: This middleware is kept as a fallback for views that don't
        # manually create ViewEvents. Reader views (ChapterDetailView, BookDetailView)
        # create ViewEvents directly in get_context_data() to make view_event_id
        # available in templates. This middleware will skip tracking if the view
        # already set request.view_event_id.
        try:
            # Skip if view already created a ViewEvent
            if hasattr(request, 'view_event_id'):
                return response

            # Track chapter view if marked by view (fallback pattern)
            if hasattr(request, "_track_chapter_view"):
                chapter = request._track_chapter_view
                view_event = StatsService.track_chapter_view(chapter, request)
                request.view_event_id = view_event.id

            # Track book view if marked by view (fallback pattern)
            if hasattr(request, "_track_book_view"):
                book = request._track_book_view
                view_event = StatsService.track_book_view(book, request)
                request.view_event_id = view_event.id

        except Exception as e:
            # Don't break the response if stats tracking fails
            logger.error(f"Stats tracking failed: {e}")

        return response
