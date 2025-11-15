"""
Chapter caching for chapter lists and navigation.

These are used for book detail pages and chapter navigation, with moderate TTL
(15-30 minutes) to balance freshness and performance.
"""

from django.core.cache import cache

from books.models import Chapter
from . import TIMEOUT_LISTS, TIMEOUT_NAVIGATION


def get_cached_book_chapters(book_id, page_number=1, per_page=20):
    """
    Get paginated published chapters for a book from cache or database.

    Cache key: book:{book_id}:chapters:page:{page_number}
    TTL: 15 minutes
    Invalidated by: Chapter save/delete signals

    Args:
        book_id: The book's primary key
        page_number: Page number for pagination (default: 1)
        per_page: Chapters per page (default: 20)

    Returns:
        dict: Contains 'chapters' list and pagination metadata
    """
    cache_key = f"book:{book_id}:chapters:page:{page_number}"
    result = cache.get(cache_key)

    if result is None:
        from django.core.paginator import Paginator

        all_chapters = list(
            Chapter.objects.filter(book_id=book_id, is_public=True)
            .select_related("chaptermaster")
            .order_by("chaptermaster__chapter_number")
        )

        paginator = Paginator(all_chapters, per_page)
        page_obj = paginator.get_page(page_number)

        result = {
            "chapters": list(page_obj),
            "has_next": page_obj.has_next(),
            "has_previous": page_obj.has_previous(),
            "num_pages": paginator.num_pages,
            "total_count": paginator.count,
        }
        cache.set(cache_key, result, timeout=TIMEOUT_LISTS)

    return result


def invalidate_book_chapter_caches(book_id):
    """
    Invalidate all chapter-related caches for a book.
    This is a brute-force approach that clears all pages.

    Args:
        book_id: The book's primary key
    """
    # We can't easily know all page numbers, so we use a pattern delete
    # Note: This requires django-redis backend which supports pattern deletion
    from django_redis import get_redis_connection

    try:
        redis_conn = get_redis_connection("default")
        # Delete all chapter page caches for this book
        pattern = f"webnovel:1:book:{book_id}:chapters:page:*"
        keys = redis_conn.keys(pattern)
        if keys:
            redis_conn.delete(*keys)
    except Exception:
        # Fallback: just delete common pages if pattern delete fails
        for page in range(1, 11):  # Clear first 10 pages
            cache.delete(f"book:{book_id}:chapters:page:{page}")


def get_cached_chapter_navigation(book_id, chapter_number):
    """
    Get chapter navigation data (previous/next/position) from cache or database.

    Cache key: chapter:nav:{book_id}:{chapter_number}
    TTL: 30 minutes
    Invalidated by: Chapter save/delete signals

    This caches the expensive navigation queries (previous/next lookups and counts).
    The actual chapter content is NOT cached to save memory.

    Args:
        book_id: The book's primary key
        chapter_number: The chapter's number in the sequence

    Returns:
        dict: Contains previous_chapter, next_chapter, position, total
    """
    cache_key = f"chapter:nav:{book_id}:{chapter_number}"
    nav_data = cache.get(cache_key)

    if nav_data is None:
        published = (
            Chapter.objects.filter(book_id=book_id, is_public=True)
            .select_related("chaptermaster")
            .order_by("chaptermaster__chapter_number")
        )

        # Get previous chapter
        previous = (
            published.filter(chaptermaster__chapter_number__lt=chapter_number)
            .values("id", "slug", "title", "chaptermaster__chapter_number")
            .last()
        )

        # Get next chapter
        next_ch = (
            published.filter(chaptermaster__chapter_number__gt=chapter_number)
            .values("id", "slug", "title", "chaptermaster__chapter_number")
            .first()
        )

        # Calculate position
        position = published.filter(
            chaptermaster__chapter_number__lte=chapter_number
        ).count()

        total = published.count()

        nav_data = {
            "previous": previous,
            "next": next_ch,
            "position": position,
            "total": total,
        }

        cache.set(cache_key, nav_data, timeout=TIMEOUT_NAVIGATION)

    return nav_data


def invalidate_chapter_navigation(book_id):
    """
    Invalidate all chapter navigation caches for a book.
    Called when chapters are added/removed/reordered.

    Args:
        book_id: The book's primary key
    """
    from django_redis import get_redis_connection

    try:
        redis_conn = get_redis_connection("default")
        # Delete all navigation caches for chapters in this book
        pattern = f"webnovel:1:chapter:nav:{book_id}:*"
        keys = redis_conn.keys(pattern)
        if keys:
            redis_conn.delete(*keys)
    except Exception:
        # Fallback: can't clear individual chapters without knowing all chapter numbers
        # Cache will expire naturally in 30 minutes
        pass
