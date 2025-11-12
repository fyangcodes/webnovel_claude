"""
Celery tasks for analytics and stats aggregation.

These tasks handle:
- Aggregating Redis counters to database stats
- Updating unique view counts across time periods
- Cleaning up old view events
- Calculating trending scores for books and chapters
"""

from celery import shared_task
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from django.db.models import Sum
from datetime import timedelta
import logging
import math

logger = logging.getLogger(__name__)


@shared_task
def aggregate_stats_hourly():
    """
    Aggregate Redis counters to PostgreSQL stats models.
    Runs every hour via Celery Beat.
    """
    from books.models import Chapter, Book, ChapterStats, BookStats
    from books.stats import StatsService

    redis_client = StatsService._get_redis_client()
    if not redis_client:
        logger.warning("Redis not available, skipping stats aggregation")
        return

    stats_updated = {"chapters": 0, "books": 0}

    # Aggregate chapter stats
    chapter_keys = redis_client.keys(f"{StatsService.REDIS_PREFIX}:chapter:*:views")
    for key in chapter_keys:
        try:
            # Extract chapter ID from key
            key_str = key.decode("utf-8") if isinstance(key, bytes) else key
            chapter_id = int(key_str.split(":")[2])

            # Get view count from Redis
            view_count = int(redis_client.get(key) or 0)
            if view_count == 0:
                continue

            # Get completion count
            completion_key = f"{StatsService.REDIS_PREFIX}:chapter:{chapter_id}:completions"
            completion_count = int(redis_client.get(completion_key) or 0)

            # Update ChapterStats
            chapter = Chapter.objects.get(id=chapter_id)
            stats, created = ChapterStats.objects.get_or_create(chapter=chapter)

            stats.total_views += view_count
            if completion_count > 0:
                stats.completion_count += completion_count
            stats.last_viewed_at = timezone.now()
            stats.save()

            # Reset Redis counters
            redis_client.delete(key)
            if completion_count > 0:
                redis_client.delete(completion_key)

            stats_updated["chapters"] += 1

        except (ValueError, Chapter.DoesNotExist) as e:
            logger.warning(f"Failed to aggregate chapter stats for key {key}: {e}")
            continue

    # Aggregate book stats
    book_keys = redis_client.keys(f"{StatsService.REDIS_PREFIX}:book:*:views")
    for key in book_keys:
        try:
            # Extract book ID from key
            key_str = key.decode("utf-8") if isinstance(key, bytes) else key
            book_id = int(key_str.split(":")[2])

            # Get view count from Redis
            view_count = int(redis_client.get(key) or 0)
            if view_count == 0:
                continue

            # Update BookStats
            book = Book.objects.get(id=book_id)
            stats, created = BookStats.objects.get_or_create(book=book)

            stats.total_views += view_count
            stats.last_viewed_at = timezone.now()
            stats.save()

            # Reset Redis counter
            redis_client.delete(key)

            stats_updated["books"] += 1

        except (ValueError, Book.DoesNotExist) as e:
            logger.warning(f"Failed to aggregate book stats for key {key}: {e}")
            continue

    logger.info(
        f"Stats aggregation complete: {stats_updated['chapters']} chapters, "
        f"{stats_updated['books']} books updated"
    )

    return stats_updated


@shared_task
def update_time_period_uniques():
    """
    Update unique view counts for different time periods (24h, 7d, 30d).
    Runs daily via Celery Beat.
    """
    from books.models import Chapter, Book, ChapterStats, BookStats, ViewEvent

    now = timezone.now()
    counts_updated = {"chapters": 0, "books": 0}

    # Get content types
    chapter_ct = ContentType.objects.get_for_model(Chapter)
    book_ct = ContentType.objects.get_for_model(Book)

    # Update chapter unique counts
    for stats in ChapterStats.objects.all():
        try:
            # 24 hour uniques
            cutoff_24h = now - timedelta(hours=24)
            stats.unique_views_24h = (
                ViewEvent.objects.filter(
                    content_type=chapter_ct,
                    object_id=stats.chapter_id,
                    viewed_at__gte=cutoff_24h,
                )
                .values("session_key")
                .distinct()
                .count()
            )

            # 7 day uniques
            cutoff_7d = now - timedelta(days=7)
            stats.unique_views_7d = (
                ViewEvent.objects.filter(
                    content_type=chapter_ct,
                    object_id=stats.chapter_id,
                    viewed_at__gte=cutoff_7d,
                )
                .values("session_key")
                .distinct()
                .count()
            )

            # 30 day uniques
            cutoff_30d = now - timedelta(days=30)
            stats.unique_views_30d = (
                ViewEvent.objects.filter(
                    content_type=chapter_ct,
                    object_id=stats.chapter_id,
                    viewed_at__gte=cutoff_30d,
                )
                .values("session_key")
                .distinct()
                .count()
            )

            # All time uniques
            stats.unique_views_all_time = (
                ViewEvent.objects.filter(
                    content_type=chapter_ct,
                    object_id=stats.chapter_id,
                )
                .values("session_key")
                .distinct()
                .count()
            )

            # Update total read time from ViewEvents
            read_time_sum = ViewEvent.objects.filter(
                content_type=chapter_ct,
                object_id=stats.chapter_id,
                read_duration_seconds__isnull=False,
            ).aggregate(total=Sum("read_duration_seconds"))["total"] or 0

            stats.total_read_time_seconds = read_time_sum

            stats.save()
            counts_updated["chapters"] += 1

        except Exception as e:
            logger.warning(f"Failed to update chapter stats {stats.chapter_id}: {e}")
            continue

    # Update book unique counts
    for stats in BookStats.objects.all():
        try:
            # 24 hour uniques
            cutoff_24h = now - timedelta(hours=24)
            stats.unique_readers_24h = (
                ViewEvent.objects.filter(
                    content_type=book_ct,
                    object_id=stats.book_id,
                    viewed_at__gte=cutoff_24h,
                )
                .values("session_key")
                .distinct()
                .count()
            )

            # 7 day uniques
            cutoff_7d = now - timedelta(days=7)
            stats.unique_readers_7d = (
                ViewEvent.objects.filter(
                    content_type=book_ct,
                    object_id=stats.book_id,
                    viewed_at__gte=cutoff_7d,
                )
                .values("session_key")
                .distinct()
                .count()
            )

            # 30 day uniques
            cutoff_30d = now - timedelta(days=30)
            stats.unique_readers_30d = (
                ViewEvent.objects.filter(
                    content_type=book_ct,
                    object_id=stats.book_id,
                    viewed_at__gte=cutoff_30d,
                )
                .values("session_key")
                .distinct()
                .count()
            )

            # All time uniques
            stats.unique_readers_all_time = (
                ViewEvent.objects.filter(
                    content_type=book_ct,
                    object_id=stats.book_id,
                )
                .values("session_key")
                .distinct()
                .count()
            )

            # Update total read time from ViewEvents
            read_time_sum = ViewEvent.objects.filter(
                content_type=book_ct,
                object_id=stats.book_id,
                read_duration_seconds__isnull=False,
            ).aggregate(total=Sum("read_duration_seconds"))["total"] or 0

            stats.total_read_time_seconds = read_time_sum

            stats.save()
            counts_updated["books"] += 1

        except Exception as e:
            logger.warning(f"Failed to update book stats {stats.book_id}: {e}")
            continue

    logger.info(
        f"Unique counts updated: {counts_updated['chapters']} chapters, "
        f"{counts_updated['books']} books"
    )

    return counts_updated


@shared_task
def cleanup_old_view_events():
    """
    Delete ViewEvent records older than retention period.
    Runs daily via Celery Beat.
    Aggregated stats are preserved in ChapterStats/BookStats.
    """
    from django.conf import settings
    from books.models import ViewEvent

    # Get retention days from settings (default 90 days)
    retention_days = getattr(settings, "STATS_CONFIG", {}).get(
        "view_event_retention_days", 90
    )

    cutoff = timezone.now() - timedelta(days=retention_days)
    deleted_count, _ = ViewEvent.objects.filter(viewed_at__lt=cutoff).delete()

    logger.info(f"Deleted {deleted_count} ViewEvents older than {retention_days} days")

    return {"deleted": deleted_count, "retention_days": retention_days}


@shared_task
def calculate_trending_scores():
    """
    Calculate trending scores for books and chapters.
    Runs every 6 hours via Celery Beat.
    Stores results in Redis sorted sets for fast retrieval.
    """
    from books.models import Book, ViewEvent
    from books.stats import StatsService

    redis_client = StatsService._get_redis_client()
    if not redis_client:
        logger.warning("Redis not available, skipping trending calculation")
        return

    now = timezone.now()

    # Calculate trending books per language
    languages = Book.objects.values_list("language__code", flat=True).distinct()

    for lang_code in languages:
        if not lang_code:
            continue

        # Get books in this language
        books = Book.objects.filter(language__code=lang_code, is_public=True)

        book_ct = ContentType.objects.get_for_model(Book)

        trending_scores = []

        for book in books:
            # Count views in last 7 days with time decay
            views_by_day = {}

            for i in range(7):
                day_start = now - timedelta(days=i)
                day_end = day_start + timedelta(days=1)

                day_views = ViewEvent.objects.filter(
                    content_type=book_ct,
                    object_id=book.id,
                    viewed_at__gte=day_start,
                    viewed_at__lt=day_end,
                ).count()

                # Apply time decay (more recent = higher weight)
                weight = math.exp(-i * 0.2)  # Exponential decay
                views_by_day[i] = day_views * weight

            # Calculate trending score
            score = sum(views_by_day.values())

            if score > 0:
                trending_scores.append((book.id, score))

        # Store in Redis sorted set
        redis_key = f"{StatsService.REDIS_PREFIX}:trending:books:{lang_code}:7d"
        redis_client.delete(redis_key)  # Clear old scores

        for book_id, score in trending_scores:
            redis_client.zadd(redis_key, {book_id: score})

        # Expire after 12 hours (will be refreshed by next run)
        redis_client.expire(redis_key, 12 * 3600)

        logger.info(f"Updated trending scores for {len(trending_scores)} books in {lang_code}")

    return {"status": "completed", "languages_processed": len(languages)}
