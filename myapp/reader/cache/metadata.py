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


# ==============================================================================
# BULK CACHE FUNCTIONS
# ==============================================================================


def get_cached_chapter_counts_bulk(book_ids):
    """
    Get chapter counts for multiple books in one cache operation.

    Uses cache.get_many() for efficiency.

    Args:
        book_ids: List of book IDs

    Returns:
        dict: {book_id: chapter_count}
    """
    if not book_ids:
        return {}

    # Build cache keys
    cache_keys = [f"book:{book_id}:chapters:count" for book_id in book_ids]
    key_to_book_id = {f"book:{book_id}:chapters:count": book_id for book_id in book_ids}

    # Get from cache
    cached = cache.get_many(cache_keys)

    # Find missing keys
    result = {}
    missing_book_ids = []

    for cache_key, book_id in key_to_book_id.items():
        if cache_key in cached:
            result[book_id] = cached[cache_key]
        else:
            missing_book_ids.append(book_id)

    # Fetch missing from database
    if missing_book_ids:
        from django.db.models import Count

        counts = (
            Chapter.objects.filter(book_id__in=missing_book_ids, is_public=True)
            .values('book_id')
            .annotate(count=Count('id'))
        )

        counts_dict = {item['book_id']: item['count'] for item in counts}

        # Cache the fetched values
        to_cache = {}
        for book_id in missing_book_ids:
            count = counts_dict.get(book_id, 0)
            result[book_id] = count
            to_cache[f"book:{book_id}:chapters:count"] = count

        cache.set_many(to_cache, timeout=TIMEOUT_METADATA)

    return result


def get_cached_total_chapter_views_bulk(book_ids):
    """
    Get total chapter views for multiple books.

    Note: This function does NOT cache results because it includes real-time
    Redis data. It optimizes by fetching all BookStats in one query.

    Args:
        book_ids: List of book IDs

    Returns:
        dict: {book_id: total_views}
    """
    if not book_ids:
        return {}

    from books.models import BookStats

    # Fetch all book stats in one query
    book_stats_list = BookStats.objects.filter(book_id__in=book_ids)
    stats_dict = {bs.book_id: bs for bs in book_stats_list}

    result = {}
    for book_id in book_ids:
        if book_id in stats_dict:
            # Include real-time Redis counts for immediate feedback
            result[book_id] = stats_dict[book_id].get_total_chapter_views(include_realtime=True)
        else:
            result[book_id] = 0

    return result
