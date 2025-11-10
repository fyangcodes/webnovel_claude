"""
Cache utilities for the reader app.

This module provides caching functions to reduce database queries and improve
performance for high-traffic reader pages. Uses Redis as the cache backend
with semantic timeout constants defined in settings.

Cache Strategy:
- Static data (languages, genres): 1 hour TTL
- Metadata (chapter counts, stats): 30 min TTL
- Content lists (carousels, book lists): 15 min TTL
- Homepage sections: 10 min TTL
- Navigation data: 30 min TTL

Cache invalidation is handled by signals in books/signals.py
"""

from django.core.cache import cache
from django.conf import settings
from django.db.models import Max

from books.models import Book, Chapter, Language, Genre


# Cache timeout constants with fallback defaults
TIMEOUT_STATIC = getattr(settings, 'CACHE_TIMEOUT_STATIC_DATA', 3600)
TIMEOUT_METADATA = getattr(settings, 'CACHE_TIMEOUT_METADATA', 1800)
TIMEOUT_LISTS = getattr(settings, 'CACHE_TIMEOUT_CONTENT_LIST', 900)
TIMEOUT_HOMEPAGE = getattr(settings, 'CACHE_TIMEOUT_HOMEPAGE', 600)
TIMEOUT_NAVIGATION = getattr(settings, 'CACHE_TIMEOUT_NAVIGATION', 1800)


# ==============================================================================
# STATIC DATA CACHING (Languages & Genres)
# ==============================================================================

def get_cached_languages():
    """
    Get all languages from cache or database.

    Cache key: languages:all
    TTL: 1 hour (rarely changes, admin-only)
    Invalidated by: Language model save/delete signals

    Returns:
        QuerySet: All Language objects ordered by name
    """
    cache_key = 'languages:all'
    languages = cache.get(cache_key)

    if languages is None:
        languages = list(Language.objects.all().order_by('name'))
        cache.set(cache_key, languages, timeout=TIMEOUT_STATIC)

    return languages


def get_cached_genres():
    """
    Get all genres from cache or database.

    Cache key: genres:all
    TTL: 1 hour (rarely changes, admin-only)
    Invalidated by: Genre model save/delete signals

    Returns:
        QuerySet: All Genre objects ordered by name
    """
    cache_key = 'genres:all'
    genres = cache.get(cache_key)

    if genres is None:
        genres = list(Genre.objects.all().order_by('name'))
        cache.set(cache_key, genres, timeout=TIMEOUT_STATIC)

    return genres


def get_cached_featured_genres(featured_genre_ids):
    """
    Get featured genres from cache or database.

    Cache key: genres:featured
    TTL: 1 hour
    Invalidated by: Genre model save/delete signals

    Args:
        featured_genre_ids: List of genre IDs to fetch

    Returns:
        QuerySet: Featured Genre objects
    """
    if not featured_genre_ids:
        return []

    cache_key = 'genres:featured'
    genres = cache.get(cache_key)

    if genres is None:
        genres = list(Genre.objects.filter(id__in=featured_genre_ids))
        cache.set(cache_key, genres, timeout=TIMEOUT_STATIC)

    return genres


# ==============================================================================
# METADATA CACHING (Counts & Stats)
# ==============================================================================

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
    cache_key = f'book:{book_id}:chapters:count'
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
    cache_key = f'book:{book_id}:chapters:count'
    cache.delete(cache_key)


# ==============================================================================
# HOMEPAGE CACHING (Carousels)
# ==============================================================================

def get_cached_featured_books(language_code, featured_bookmaster_ids):
    """
    Get featured books carousel from cache or database.

    Cache key: homepage:featured:{language_code}
    TTL: 10 minutes
    Invalidated by: Book save/delete signals, manual admin changes

    Args:
        language_code: Language code (e.g., 'en', 'zh')
        featured_bookmaster_ids: List of bookmaster IDs to feature

    Returns:
        list: Featured Book objects with relationships prefetched
    """
    if not featured_bookmaster_ids:
        return []

    cache_key = f'homepage:featured:{language_code}'
    books = cache.get(cache_key)

    if books is None:
        books = list(
            Book.objects.filter(
                bookmaster_id__in=featured_bookmaster_ids,
                language__code=language_code,
                is_public=True
            )
            .select_related('bookmaster', 'language')
            .prefetch_related('chapters', 'bookmaster__genres')
        )
        cache.set(cache_key, books, timeout=TIMEOUT_HOMEPAGE)

    return books


def get_cached_recently_updated(language_code, limit=6):
    """
    Get recently updated books (by latest chapter) from cache or database.

    Cache key: homepage:recently_updated:{language_code}
    TTL: 10 minutes
    Invalidated by: Chapter save signals (when published_at changes)

    Args:
        language_code: Language code (e.g., 'en', 'zh')
        limit: Number of books to return (default: 6)

    Returns:
        list: Recently updated Book objects with latest_chapter annotation
    """
    cache_key = f'homepage:recently_updated:{language_code}'
    books = cache.get(cache_key)

    if books is None:
        books = list(
            Book.objects.filter(language__code=language_code, is_public=True)
            .select_related('bookmaster', 'language')
            .prefetch_related('chapters', 'bookmaster__genres')
            .annotate(latest_chapter=Max('chapters__published_at'))
            .order_by('-latest_chapter')[:limit]
        )
        cache.set(cache_key, books, timeout=TIMEOUT_HOMEPAGE)

    return books


def get_cached_new_arrivals(language_code, limit=6):
    """
    Get recently published books from cache or database.

    Cache key: homepage:new_arrivals:{language_code}
    TTL: 10 minutes
    Invalidated by: Book save signals (when published_at changes)

    Args:
        language_code: Language code (e.g., 'en', 'zh')
        limit: Number of books to return (default: 6)

    Returns:
        list: Recently published Book objects
    """
    cache_key = f'homepage:new_arrivals:{language_code}'
    books = cache.get(cache_key)

    if books is None:
        books = list(
            Book.objects.filter(language__code=language_code, is_public=True)
            .select_related('bookmaster', 'language')
            .prefetch_related('chapters', 'bookmaster__genres')
            .order_by('-published_at')[:limit]
        )
        cache.set(cache_key, books, timeout=TIMEOUT_HOMEPAGE)

    return books


def invalidate_homepage_caches(language_code):
    """
    Invalidate all homepage caches for a specific language.
    Called by signals when books or chapters are published/updated.

    Args:
        language_code: Language code to invalidate caches for
    """
    cache.delete(f'homepage:featured:{language_code}')
    cache.delete(f'homepage:recently_updated:{language_code}')
    cache.delete(f'homepage:new_arrivals:{language_code}')


# ==============================================================================
# BOOK DETAIL CACHING
# ==============================================================================

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
    cache_key = f'book:{book_id}:chapters:page:{page_number}'
    result = cache.get(cache_key)

    if result is None:
        from django.core.paginator import Paginator

        all_chapters = list(
            Chapter.objects.filter(book_id=book_id, is_public=True)
            .select_related('chaptermaster')
            .order_by('chaptermaster__chapter_number')
        )

        paginator = Paginator(all_chapters, per_page)
        page_obj = paginator.get_page(page_number)

        result = {
            'chapters': list(page_obj),
            'has_next': page_obj.has_next(),
            'has_previous': page_obj.has_previous(),
            'num_pages': paginator.num_pages,
            'total_count': paginator.count,
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
        redis_conn = get_redis_connection('default')
        # Delete all chapter page caches for this book
        pattern = f'webnovel:1:book:{book_id}:chapters:page:*'
        keys = redis_conn.keys(pattern)
        if keys:
            redis_conn.delete(*keys)
    except Exception:
        # Fallback: just delete common pages if pattern delete fails
        for page in range(1, 11):  # Clear first 10 pages
            cache.delete(f'book:{book_id}:chapters:page:{page}')


# ==============================================================================
# CHAPTER NAVIGATION CACHING
# ==============================================================================

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
    cache_key = f'chapter:nav:{book_id}:{chapter_number}'
    nav_data = cache.get(cache_key)

    if nav_data is None:
        published = Chapter.objects.filter(
            book_id=book_id,
            is_public=True
        ).select_related('chaptermaster').order_by('chaptermaster__chapter_number')

        # Get previous chapter
        previous = published.filter(
            chaptermaster__chapter_number__lt=chapter_number
        ).values('id', 'slug', 'title', 'chaptermaster__chapter_number').last()

        # Get next chapter
        next_ch = published.filter(
            chaptermaster__chapter_number__gt=chapter_number
        ).values('id', 'slug', 'title', 'chaptermaster__chapter_number').first()

        # Calculate position
        position = published.filter(
            chaptermaster__chapter_number__lte=chapter_number
        ).count()

        total = published.count()

        nav_data = {
            'previous': previous,
            'next': next_ch,
            'position': position,
            'total': total
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
        redis_conn = get_redis_connection('default')
        # Delete all navigation caches for chapters in this book
        pattern = f'webnovel:1:chapter:nav:{book_id}:*'
        keys = redis_conn.keys(pattern)
        if keys:
            redis_conn.delete(*keys)
    except Exception:
        # Fallback: can't clear individual chapters without knowing all chapter numbers
        # Cache will expire naturally in 30 minutes
        pass
