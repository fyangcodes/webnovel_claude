"""
Homepage caching for featured books and content carousels.

These change frequently as new content is published, so we use shorter TTL
(10 minutes) to keep the homepage fresh while still reducing database load.
"""

from django.core.cache import cache
from django.db.models import Max

from books.models import Book
from . import TIMEOUT_HOMEPAGE


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

    cache_key = f"homepage:featured:{language_code}"
    books = cache.get(cache_key)

    if books is None:
        books = list(
            Book.objects.filter(
                bookmaster_id__in=featured_bookmaster_ids,
                language__code=language_code,
                is_public=True,
            ).with_card_relations()
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
    cache_key = f"homepage:recently_updated:{language_code}"
    books = cache.get(cache_key)

    if books is None:
        books = list(
            Book.objects.filter(language__code=language_code, is_public=True)
            .with_card_relations()
            .annotate(latest_chapter=Max("chapters__published_at"))
            .order_by("-latest_chapter")[:limit]
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
    cache_key = f"homepage:new_arrivals:{language_code}"
    books = cache.get(cache_key)

    if books is None:
        books = list(
            Book.objects.filter(language__code=language_code, is_public=True)
            .with_card_relations()
            .order_by("-published_at")[:limit]
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
    cache.delete(f"homepage:featured:{language_code}")
    cache.delete(f"homepage:recently_updated:{language_code}")
    cache.delete(f"homepage:new_arrivals:{language_code}")
