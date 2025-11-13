"""
API views for statistics tracking.
"""

from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from books.stats import StatsService
import json
import logging

logger = logging.getLogger(__name__)


@require_POST
@csrf_exempt  # Using sendBeacon, handle CSRF differently
def update_reading_progress(request):
    """
    API endpoint for JavaScript to update reading progress.
    Called when user leaves page via navigator.sendBeacon().

    POST data:
        view_event_id: ID of the ViewEvent
        duration: Reading duration in seconds
        completed: Whether user reached the end (boolean)

    Returns:
        JSON response with status
    """
    try:
        # Parse JSON body
        data = json.loads(request.body)

        view_event_id = data.get("view_event_id")
        duration = data.get("duration")
        completed = data.get("completed", False)

        # Validate required fields
        if not view_event_id or duration is None:
            return JsonResponse(
                {"status": "error", "message": "Missing required fields"}, status=400
            )

        # Update reading progress
        StatsService.update_reading_progress(view_event_id, duration, completed)

        return JsonResponse({"status": "ok"})

    except json.JSONDecodeError:
        logger.warning("Invalid JSON in reading progress update")
        return JsonResponse(
            {"status": "error", "message": "Invalid JSON"}, status=400
        )
    except Exception as e:
        logger.error(f"Error updating reading progress: {e}")
        return JsonResponse(
            {"status": "error", "message": "Internal server error"}, status=500
        )
