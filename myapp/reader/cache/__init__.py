"""
Cache utilities package for the reader app.

This package provides caching functions to reduce database queries and improve
performance for high-traffic reader pages. Uses Redis as the cache backend
with semantic timeout constants defined in settings.

Cache Strategy:
- Static data (languages, genres, sections, tags): 1 hour TTL
- Metadata (chapter counts, stats): 30 min TTL
- Content lists (carousels, book lists): 15 min TTL
- Homepage sections: 10 min TTL
- Navigation data: 30 min TTL

Cache invalidation is handled by signals in books/signals/cache.py

Package organization:
- static_data: Languages, genres, sections, tags
- metadata: Chapter counts and stats
- homepage: Featured books, carousels
- chapters: Chapter lists and navigation
"""

from django.conf import settings

# Cache timeout constants with fallback defaults
TIMEOUT_STATIC = getattr(settings, "CACHE_TIMEOUT_STATIC_DATA", 3600)
TIMEOUT_METADATA = getattr(settings, "CACHE_TIMEOUT_METADATA", 1800)
TIMEOUT_LISTS = getattr(settings, "CACHE_TIMEOUT_CONTENT_LIST", 900)
TIMEOUT_HOMEPAGE = getattr(settings, "CACHE_TIMEOUT_HOMEPAGE", 600)
TIMEOUT_NAVIGATION = getattr(settings, "CACHE_TIMEOUT_NAVIGATION", 1800)

# Import all cache functions
from .static_data import (
    get_cached_languages,
    get_cached_sections,
    get_cached_genres,
    get_cached_genres_flat,
    get_cached_featured_genres,
    get_cached_tags,
)

from .metadata import (
    get_cached_chapter_count,
    invalidate_chapter_count,
    get_cached_total_chapter_views,
    invalidate_total_chapter_views,
)

from .homepage import (
    get_cached_featured_books,
    get_cached_recently_updated,
    get_cached_new_arrivals,
    invalidate_homepage_caches,
)

from .chapters import (
    get_cached_book_chapters,
    invalidate_book_chapter_caches,
    get_cached_chapter_navigation,
    invalidate_chapter_navigation,
)

__all__ = [
    # Constants
    "TIMEOUT_STATIC",
    "TIMEOUT_METADATA",
    "TIMEOUT_LISTS",
    "TIMEOUT_HOMEPAGE",
    "TIMEOUT_NAVIGATION",
    # Static data
    "get_cached_languages",
    "get_cached_sections",
    "get_cached_genres",
    "get_cached_genres_flat",
    "get_cached_featured_genres",
    "get_cached_tags",
    # Metadata
    "get_cached_chapter_count",
    "invalidate_chapter_count",
    "get_cached_total_chapter_views",
    "invalidate_total_chapter_views",
    # Homepage
    "get_cached_featured_books",
    "get_cached_recently_updated",
    "get_cached_new_arrivals",
    "invalidate_homepage_caches",
    # Chapters
    "get_cached_book_chapters",
    "invalidate_book_chapter_caches",
    "get_cached_chapter_navigation",
    "invalidate_chapter_navigation",
]
