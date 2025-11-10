"""
Analytics queries for books and chapters.
Provides complex analytics using ViewEvent data.
"""

from django.contrib.contenttypes.models import ContentType
from django.db.models import Count, Avg, Sum, Q
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


class Analytics:
    """Complex analytics queries using ViewEvent and stats data"""

    @classmethod
    def get_trending_books(cls, language, days=7, limit=10):
        """
        Get trending books for a language.
        Reads from Redis sorted set if available, falls back to DB query.

        Args:
            language: Language instance or code
            days: Number of days to consider (default 7)
            limit: Max number of results (default 10)

        Returns:
            QuerySet of Book instances
        """
        from .models import Book
        from .stats import StatsService

        # Get language code
        lang_code = language.code if hasattr(language, "code") else language

        # Try to get from Redis first
        redis_client = StatsService._get_redis_client()
        if redis_client:
            try:
                redis_key = f"{StatsService.REDIS_PREFIX}:trending:books:{lang_code}:{days}d"
                # Get top book IDs from sorted set (highest scores first)
                trending_ids = redis_client.zrevrange(redis_key, 0, limit - 1)

                if trending_ids:
                    # Convert bytes to ints
                    book_ids = [
                        int(id.decode("utf-8") if isinstance(id, bytes) else id)
                        for id in trending_ids
                    ]
                    # Return books in order of trending score
                    preserved = Case(*[When(pk=pk, then=pos) for pos, pk in enumerate(book_ids)])
                    return Book.objects.filter(id__in=book_ids).order_by(preserved)

            except Exception as e:
                logger.warning(f"Failed to get trending from Redis: {e}")

        # Fallback to DB query
        from .models import ViewEvent

        cutoff = timezone.now() - timedelta(days=days)
        book_ct = ContentType.objects.get_for_model(Book)

        # Count views per book in time period
        trending = (
            ViewEvent.objects.filter(
                content_type=book_ct, viewed_at__gte=cutoff
            )
            .values("object_id")
            .annotate(view_count=Count("id"), unique_sessions=Count("session_key", distinct=True))
            .order_by("-view_count")[:limit]
        )

        book_ids = [item["object_id"] for item in trending]
        return Book.objects.filter(id__in=book_ids, language__code=lang_code, is_public=True)

    @classmethod
    def get_trending_chapters(cls, book, days=7, limit=10):
        """
        Get trending chapters for a book.

        Args:
            book: Book instance
            days: Number of days to consider
            limit: Max number of results

        Returns:
            QuerySet of Chapter instances
        """
        from .models import Chapter, ViewEvent

        cutoff = timezone.now() - timedelta(days=days)
        chapter_ct = ContentType.objects.get_for_model(Chapter)

        # Get chapter IDs for this book
        chapter_ids = book.chapters.values_list("id", flat=True)

        # Count views per chapter
        trending = (
            ViewEvent.objects.filter(
                content_type=chapter_ct, object_id__in=chapter_ids, viewed_at__gte=cutoff
            )
            .values("object_id")
            .annotate(view_count=Count("id"))
            .order_by("-view_count")[:limit]
        )

        trending_ids = [item["object_id"] for item in trending]
        return Chapter.objects.filter(id__in=trending_ids)

    @classmethod
    def calculate_retention_curve(cls, book):
        """
        Calculate chapter-by-chapter retention curve.
        Shows how many readers drop off at each chapter.

        Args:
            book: Book instance

        Returns:
            List of dicts: [
                {'chapter_number': 1, 'readers': 1000, 'retention': 100},
                {'chapter_number': 2, 'readers': 670, 'retention': 67},
                ...
            ]
        """
        from .models import Chapter, ViewEvent

        chapter_ct = ContentType.objects.get_for_model(Chapter)

        # Get all chapters for this book, ordered by chapter number
        chapters = book.chapters.filter(is_public=True).select_related("chaptermaster").order_by(
            "chaptermaster__chapter_number"
        )

        retention_data = []
        first_chapter_readers = None

        for chapter in chapters:
            # Count unique sessions for this chapter
            unique_readers = (
                ViewEvent.objects.filter(content_type=chapter_ct, object_id=chapter.id)
                .values("session_key")
                .distinct()
                .count()
            )

            # Track first chapter readers for retention calculation
            if first_chapter_readers is None:
                first_chapter_readers = unique_readers

            # Calculate retention percentage
            retention = (unique_readers / first_chapter_readers * 100) if first_chapter_readers > 0 else 0

            retention_data.append(
                {
                    "chapter_number": chapter.chaptermaster.chapter_number,
                    "chapter_id": chapter.id,
                    "chapter_title": chapter.title,
                    "readers": unique_readers,
                    "retention": round(retention, 2),
                }
            )

        return retention_data

    @classmethod
    def get_chapter_completion_rate(cls, chapter):
        """
        Calculate completion rate for a chapter.

        Args:
            chapter: Chapter instance

        Returns:
            float: Percentage of readers who completed the chapter
        """
        from .models import ViewEvent

        chapter_ct = ContentType.objects.get_for_model(chapter)

        total_views = ViewEvent.objects.filter(content_type=chapter_ct, object_id=chapter.id).count()

        if total_views == 0:
            return 0.0

        completed_views = ViewEvent.objects.filter(
            content_type=chapter_ct, object_id=chapter.id, completed=True
        ).count()

        return (completed_views / total_views) * 100

    @classmethod
    def get_reading_time_distribution(cls, chapter):
        """
        Get reading time statistics for a chapter.

        Args:
            chapter: Chapter instance

        Returns:
            dict with avg, median, min, max reading times
        """
        from .models import ViewEvent

        chapter_ct = ContentType.objects.get_for_model(chapter)

        # Get all reading durations
        durations = ViewEvent.objects.filter(
            content_type=chapter_ct,
            object_id=chapter.id,
            read_duration_seconds__isnull=False,
            read_duration_seconds__gt=0,  # Exclude zero durations
        ).aggregate(
            avg=Avg("read_duration_seconds"),
            total=Sum("read_duration_seconds"),
            count=Count("id"),
        )

        # Get estimated reading time from chapter
        estimated_seconds = chapter.reading_time_minutes * 60

        return {
            "average_seconds": int(durations["avg"] or 0),
            "average_minutes": round((durations["avg"] or 0) / 60, 2),
            "total_seconds": int(durations["total"] or 0),
            "count": durations["count"],
            "estimated_seconds": estimated_seconds,
            "estimated_minutes": chapter.reading_time_minutes,
        }

    @classmethod
    def get_popular_reading_hours(cls, days=30):
        """
        Get popular reading hours (0-23).

        Args:
            days: Number of days to analyze

        Returns:
            List of dicts: [{'hour': 14, 'views': 234}, ...]
        """
        from .models import ViewEvent
        from django.db.models.functions import ExtractHour

        cutoff = timezone.now() - timedelta(days=days)

        hourly_stats = (
            ViewEvent.objects.filter(viewed_at__gte=cutoff)
            .annotate(hour=ExtractHour("viewed_at"))
            .values("hour")
            .annotate(view_count=Count("id"))
            .order_by("hour")
        )

        return list(hourly_stats)

    @classmethod
    def get_traffic_sources(cls, content_object, days=30):
        """
        Get traffic sources (referrers) for content.

        Args:
            content_object: Chapter or Book instance
            days: Number of days to analyze

        Returns:
            List of dicts: [{'source': 'google.com', 'count': 234}, ...]
        """
        from .models import ViewEvent
        from urllib.parse import urlparse

        content_type = ContentType.objects.get_for_model(content_object)
        cutoff = timezone.now() - timedelta(days=days)

        # Get all referrers
        referrers = (
            ViewEvent.objects.filter(
                content_type=content_type,
                object_id=content_object.id,
                viewed_at__gte=cutoff,
                referrer__isnull=False,
            )
            .exclude(referrer="")
            .values_list("referrer", flat=True)
        )

        # Parse domains from referrers
        sources = {}
        direct_count = ViewEvent.objects.filter(
            content_type=content_type,
            object_id=content_object.id,
            viewed_at__gte=cutoff,
        ).filter(Q(referrer__isnull=True) | Q(referrer="")).count()

        if direct_count > 0:
            sources["direct"] = direct_count

        for referrer in referrers:
            try:
                parsed = urlparse(referrer)
                domain = parsed.netloc or "direct"
                sources[domain] = sources.get(domain, 0) + 1
            except Exception:
                continue

        # Convert to sorted list
        result = [{"source": source, "count": count} for source, count in sources.items()]
        result.sort(key=lambda x: x["count"], reverse=True)

        return result

    @classmethod
    def get_device_breakdown(cls, content_object, days=30):
        """
        Get device type breakdown (mobile, desktop, tablet).

        Args:
            content_object: Chapter or Book instance
            days: Number of days to analyze

        Returns:
            dict: {'mobile': 45.2, 'desktop': 50.3, 'tablet': 4.5}
        """
        from .models import ViewEvent

        content_type = ContentType.objects.get_for_model(content_object)
        cutoff = timezone.now() - timedelta(days=days)

        # Get all user agents
        user_agents = ViewEvent.objects.filter(
            content_type=content_type,
            object_id=content_object.id,
            viewed_at__gte=cutoff,
            user_agent__isnull=False,
        ).values_list("user_agent", flat=True)

        total = len(list(user_agents))
        if total == 0:
            return {"mobile": 0, "desktop": 0, "tablet": 0}

        device_counts = {"mobile": 0, "desktop": 0, "tablet": 0}

        for ua in user_agents:
            ua_lower = ua.lower()

            if "mobile" in ua_lower or "android" in ua_lower:
                device_counts["mobile"] += 1
            elif "tablet" in ua_lower or "ipad" in ua_lower:
                device_counts["tablet"] += 1
            else:
                device_counts["desktop"] += 1

        # Convert to percentages
        return {
            "mobile": round((device_counts["mobile"] / total) * 100, 2),
            "desktop": round((device_counts["desktop"] / total) * 100, 2),
            "tablet": round((device_counts["tablet"] / total) * 100, 2),
        }

    @classmethod
    def get_popular_genres(cls, language, days=30, limit=10):
        """
        Get popular genres based on view counts.

        Args:
            language: Language instance or code
            days: Number of days to analyze
            limit: Max number of genres to return

        Returns:
            List of dicts with genre and view count
        """
        from .models import Book, ViewEvent, BookGenre

        lang_code = language.code if hasattr(language, "code") else language
        cutoff = timezone.now() - timedelta(days=days)

        book_ct = ContentType.objects.get_for_model(Book)

        # Get view counts per book
        book_views = (
            ViewEvent.objects.filter(
                content_type=book_ct, viewed_at__gte=cutoff
            )
            .values("object_id")
            .annotate(view_count=Count("id"))
        )

        # Map book IDs to view counts
        view_map = {item["object_id"]: item["view_count"] for item in book_views}

        # Get books in this language
        books = Book.objects.filter(language__code=lang_code, id__in=view_map.keys())

        # Aggregate views by genre
        genre_stats = {}

        for book_genre in BookGenre.objects.filter(
            bookmaster__books__in=books
        ).select_related("genre"):
            genre_name = book_genre.genre.name
            book_id = book_genre.bookmaster.books.filter(language__code=lang_code).first().id

            if book_id in view_map:
                genre_stats[genre_name] = genre_stats.get(genre_name, 0) + view_map[book_id]

        # Sort by view count
        result = [{"genre": genre, "views": views} for genre, views in genre_stats.items()]
        result.sort(key=lambda x: x["views"], reverse=True)

        return result[:limit]


# Import for preserved ordering in get_trending_books
from django.db.models import Case, When

