"""
Statistics tracking service for books and chapters.
Handles view tracking, engagement metrics, and analytics using Redis + PostgreSQL.
"""

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from django.core.cache import cache
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


class StatsService:
    """Service for tracking and retrieving statistics"""

    REDIS_PREFIX = "stats"
    CACHE_TTL = 3600  # 1 hour cache for aggregated stats

    @classmethod
    def track_chapter_view(cls, chapter, request):
        """
        Track a chapter view event.
        Creates ViewEvent and increments Redis counters.

        Args:
            chapter: Chapter instance
            request: Django request object

        Returns:
            ViewEvent instance
        """
        from .models import ViewEvent, ChapterStats

        # Ensure session exists
        session_key = cls.ensure_session_exists(request)

        # Get content type for chapter
        content_type = ContentType.objects.get_for_model(chapter)

        # Create ViewEvent
        view_event = ViewEvent.objects.create(
            content_type=content_type,
            object_id=chapter.id,
            session_key=session_key,
            user_agent=request.META.get("HTTP_USER_AGENT", "")[:500],
            referrer=request.META.get("HTTP_REFERER", "")[:500],
        )

        # Increment Redis counters (for real-time stats)
        try:
            cls._increment_chapter_counters(chapter.id, session_key)
        except Exception as e:
            logger.warning(f"Failed to update Redis counters for chapter {chapter.id}: {e}")

        # Ensure ChapterStats exists
        cls.get_or_create_stats(chapter)

        return view_event

    @classmethod
    def track_book_view(cls, book, request):
        """
        Track a book view event.
        Creates ViewEvent and increments Redis counters.

        Args:
            book: Book instance
            request: Django request object

        Returns:
            ViewEvent instance
        """
        from .models import ViewEvent, BookStats

        # Ensure session exists
        session_key = cls.ensure_session_exists(request)

        # Get content type for book
        content_type = ContentType.objects.get_for_model(book)

        # Create ViewEvent
        view_event = ViewEvent.objects.create(
            content_type=content_type,
            object_id=book.id,
            session_key=session_key,
            user_agent=request.META.get("HTTP_USER_AGENT", "")[:500],
            referrer=request.META.get("HTTP_REFERER", "")[:500],
        )

        # Increment Redis counters (for real-time stats)
        try:
            cls._increment_book_counters(book.id, session_key)
        except Exception as e:
            logger.warning(f"Failed to update Redis counters for book {book.id}: {e}")

        # Ensure BookStats exists
        cls.get_or_create_stats(book)

        return view_event

    @classmethod
    def update_reading_progress(cls, view_event_id, duration_seconds, completed):
        """
        Update reading progress for a ViewEvent.
        Called by JavaScript when user leaves page.

        Args:
            view_event_id: ViewEvent ID
            duration_seconds: Time spent reading
            completed: Whether user reached the end
        """
        from .models import ViewEvent

        try:
            view_event = ViewEvent.objects.get(id=view_event_id)
            view_event.read_duration_seconds = duration_seconds
            view_event.completed = completed
            view_event.save(update_fields=["read_duration_seconds", "completed"])

            # Update Redis completion counters if completed
            if completed:
                cls._increment_completion_counter(
                    view_event.content_type_id, view_event.object_id
                )

        except ViewEvent.DoesNotExist:
            logger.warning(f"ViewEvent {view_event_id} not found")

    @classmethod
    def get_chapter_stats(cls, chapter, include_realtime=True):
        """
        Get statistics for a chapter.

        Args:
            chapter: Chapter instance
            include_realtime: Whether to merge Redis real-time data

        Returns:
            dict with stats
        """
        from .models import ChapterStats

        # Get or create stats
        stats, created = ChapterStats.objects.get_or_create(chapter=chapter)

        result = {
            "total_views": stats.total_views,
            "unique_views_24h": stats.unique_views_24h,
            "unique_views_7d": stats.unique_views_7d,
            "unique_views_30d": stats.unique_views_30d,
            "unique_views_all_time": stats.unique_views_all_time,
            "total_read_time_seconds": stats.total_read_time_seconds,
            "average_read_time_seconds": stats.average_read_time_seconds,
            "completion_count": stats.completion_count,
            "completion_rate": stats.completion_rate,
            "last_viewed_at": stats.last_viewed_at,
        }

        # Optionally merge real-time Redis data
        if include_realtime:
            try:
                redis_views = cls._get_redis_counter(f"chapter:{chapter.id}:views")
                if redis_views:
                    result["total_views"] += redis_views
            except Exception as e:
                logger.warning(f"Failed to get Redis stats for chapter {chapter.id}: {e}")

        return result

    @classmethod
    def get_book_stats(cls, book, include_realtime=True):
        """
        Get statistics for a book.

        Args:
            book: Book instance
            include_realtime: Whether to merge Redis real-time data

        Returns:
            dict with stats
        """
        from .models import BookStats

        # Get or create stats
        stats, created = BookStats.objects.get_or_create(book=book)

        result = {
            "total_views": stats.total_views,
            "unique_readers_24h": stats.unique_readers_24h,
            "unique_readers_7d": stats.unique_readers_7d,
            "unique_readers_30d": stats.unique_readers_30d,
            "unique_readers_all_time": stats.unique_readers_all_time,
            "total_read_time_seconds": stats.total_read_time_seconds,
            "average_read_time_seconds": stats.average_read_time_seconds,
            "last_viewed_at": stats.last_viewed_at,
        }

        # Optionally merge real-time Redis data
        if include_realtime:
            try:
                redis_views = cls._get_redis_counter(f"book:{book.id}:views")
                if redis_views:
                    result["total_views"] += redis_views
            except Exception as e:
                logger.warning(f"Failed to get Redis stats for book {book.id}: {e}")

        return result

    @classmethod
    def ensure_session_exists(cls, request):
        """
        Ensure Django session exists and return session key.

        Args:
            request: Django request object

        Returns:
            session_key string
        """
        if not request.session.session_key:
            request.session.create()
        return request.session.session_key

    @classmethod
    def get_or_create_stats(cls, content_object):
        """
        Get or create stats model for content object.

        Args:
            content_object: Chapter or Book instance

        Returns:
            ChapterStats or BookStats instance
        """
        from .models import Chapter, Book, ChapterStats, BookStats

        if isinstance(content_object, Chapter):
            stats, created = ChapterStats.objects.get_or_create(chapter=content_object)
        elif isinstance(content_object, Book):
            stats, created = BookStats.objects.get_or_create(book=content_object)
        else:
            raise ValueError(f"Unsupported content type: {type(content_object)}")

        return stats

    # Redis helper methods

    @classmethod
    def _get_redis_client(cls):
        """Get Redis client from Django cache"""
        try:
            from django_redis import get_redis_connection

            return get_redis_connection("default")
        except Exception as e:
            logger.warning(f"Failed to get Redis connection: {e}")
            return None

    @classmethod
    def _increment_chapter_counters(cls, chapter_id, session_key):
        """Increment Redis counters for chapter view"""
        redis_client = cls._get_redis_client()
        if not redis_client:
            return

        # Increment total views
        redis_client.incr(f"{cls.REDIS_PREFIX}:chapter:{chapter_id}:views")

        # Add session to daily set for unique tracking
        from datetime import date

        today = date.today().isoformat()
        redis_client.sadd(
            f"{cls.REDIS_PREFIX}:chapter:{chapter_id}:sessions:{today}", session_key
        )
        # Expire after 31 days
        redis_client.expire(
            f"{cls.REDIS_PREFIX}:chapter:{chapter_id}:sessions:{today}", 31 * 86400
        )

    @classmethod
    def _increment_book_counters(cls, book_id, session_key):
        """Increment Redis counters for book view"""
        redis_client = cls._get_redis_client()
        if not redis_client:
            return

        # Increment total views
        redis_client.incr(f"{cls.REDIS_PREFIX}:book:{book_id}:views")

        # Add session to daily set for unique tracking
        from datetime import date

        today = date.today().isoformat()
        redis_client.sadd(
            f"{cls.REDIS_PREFIX}:book:{book_id}:sessions:{today}", session_key
        )
        # Expire after 31 days
        redis_client.expire(
            f"{cls.REDIS_PREFIX}:book:{book_id}:sessions:{today}", 31 * 86400
        )

    @classmethod
    def _increment_completion_counter(cls, content_type_id, object_id):
        """Increment completion counter in Redis"""
        redis_client = cls._get_redis_client()
        if not redis_client:
            return

        # Only track chapter completions for now
        from .models import Chapter

        ct = ContentType.objects.get_for_id(content_type_id)
        if ct.model_class() == Chapter:
            redis_client.incr(f"{cls.REDIS_PREFIX}:chapter:{object_id}:completions")

    @classmethod
    def _get_redis_counter(cls, key):
        """Get counter value from Redis"""
        redis_client = cls._get_redis_client()
        if not redis_client:
            return 0

        value = redis_client.get(f"{cls.REDIS_PREFIX}:{key}")
        return int(value) if value else 0
