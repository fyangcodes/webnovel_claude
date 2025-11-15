"""
Metadata caching for chapter counts and book statistics.

These change more frequently than static data but are still expensive to compute,
so we use moderate TTL (30 minutes) and invalidate via signals.
"""

from django.core.cache import cache

from books.models import Chapter
from . import TIMEOUT_METADATA


def get_cached_chapter_count(book_id):
    """
    Get published chapter count for a book from cache or database.

    Cache key: book:{book_id}:chapters:count
    TTL: 30 minutes
    Invalidated by: Chapter save/delete signals

    This is the most important cache for solving N+1 query problems in list views.

    Args:
        book_id: The book's primary key

    Returns:
        int: Number of published chapters
    """
    cache_key = f"book:{book_id}:chapters:count"
    count = cache.get(cache_key)

    if count is None:
        count = Chapter.objects.filter(book_id=book_id, is_public=True).count()
        cache.set(cache_key, count, timeout=TIMEOUT_METADATA)

    return count


def invalidate_chapter_count(book_id):
    """
    Manually invalidate the chapter count cache for a book.
    Called by signals when chapters are published/unpublished.

    Args:
        book_id: The book's primary key
    """
    cache_key = f"book:{book_id}:chapters:count"
    cache.delete(cache_key)


def get_cached_total_chapter_views(book_id):
    """
    Get total chapter views for a book including real-time Redis counts.

    This function does NOT cache the result because it includes real-time
    Redis data that changes frequently. The underlying BookStats query
    is efficient (single aggregation query + Redis lookups).

    Args:
        book_id: The book's primary key

    Returns:
        int: Sum of total_views from all published chapters (PostgreSQL + Redis)
    """
    from books.models import BookStats

    try:
        book_stats = BookStats.objects.get(book_id=book_id)
        # Include real-time Redis counts for immediate feedback
        total_views = book_stats.get_total_chapter_views(include_realtime=True)
    except BookStats.DoesNotExist:
        total_views = 0

    return total_views


def invalidate_total_chapter_views(book_id):
    """
    Manually invalidate the total chapter views cache for a book.
    Called by signals when chapter stats are updated.

    Args:
        book_id: The book's primary key
    """
    cache_key = f"book:{book_id}:total_chapter_views"
    cache.delete(cache_key)
