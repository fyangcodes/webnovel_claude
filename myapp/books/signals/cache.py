"""
Signal handlers for cache invalidation.

This module defines signal handlers that automatically invalidate cached data
when models are created, updated, or deleted. This ensures users always see
fresh data after content changes.

Signal Priorities:
- High priority: Chapter counts, navigation (affects multiple pages)
- Medium priority: Homepage carousels (high traffic but tolerates brief staleness)
- Low priority: Static data (languages, genres - admin only, rare changes)
"""

from django.db.models.signals import post_save, post_delete, m2m_changed
from django.dispatch import receiver
from django.core.cache import cache

from books.models import Book, Chapter, Language, Genre, BookGenre, ChapterStats, Section, Tag


# ==============================================================================
# CHAPTER SIGNALS
# ==============================================================================

@receiver([post_save, post_delete], sender=Chapter)
def invalidate_chapter_caches(sender, instance, **kwargs):
    """
    Invalidate caches when a chapter is created, updated, or deleted.

    Affected caches:
    1. Chapter count for the book (N+1 query cache)
    2. Chapter navigation for the book (previous/next links)
    3. Book chapter list pages (paginated chapter lists)
    4. Homepage recently updated carousel (if chapter just published)
    5. Total chapter views for the book (when chapter is published/unpublished)
    """
    from reader.cache import (
        invalidate_chapter_count,
        invalidate_chapter_navigation,
        invalidate_book_chapter_caches,
        invalidate_homepage_caches,
        invalidate_total_chapter_views
    )

    book = instance.book
    language_code = book.language.code

    # Always invalidate chapter-specific caches
    invalidate_chapter_count(book.id)
    invalidate_chapter_navigation(book.id)
    invalidate_book_chapter_caches(book.id)
    invalidate_total_chapter_views(book.id)  # New: invalidate aggregated views

    # If chapter is public (or was just published), invalidate homepage
    if instance.is_public:
        invalidate_homepage_caches(language_code)


# ==============================================================================
# BOOK SIGNALS
# ==============================================================================

@receiver([post_save, post_delete], sender=Book)
def invalidate_book_caches(sender, instance, **kwargs):
    """
    Invalidate caches when a book is created, updated, or deleted.

    Affected caches:
    1. Homepage carousels (featured, new arrivals, recently updated)
    2. Book chapter caches (if book metadata changed)
    """
    from reader.cache import invalidate_homepage_caches

    language_code = instance.language.code

    # Invalidate homepage carousels
    invalidate_homepage_caches(language_code)

    # If book was deleted or unpublished, invalidate chapter-related caches
    if not instance.is_public or kwargs.get('created', False):
        from reader.cache import invalidate_book_chapter_caches
        invalidate_book_chapter_caches(instance.id)


# ==============================================================================
# LANGUAGE SIGNALS
# ==============================================================================

@receiver([post_save, post_delete], sender=Language)
def invalidate_language_caches(sender, instance, **kwargs):
    """
    Invalidate language caches when a language is created, updated, or deleted.

    This is rare (admin-only operation) but important for language switcher.

    Affected caches:
    1. All languages list (language switcher dropdown - staff view)
    2. Public languages list (language switcher dropdown - reader view)
    """
    cache.delete('languages:all')
    cache.delete('languages:public')


# ==============================================================================
# GENRE SIGNALS
# ==============================================================================

@receiver([post_save, post_delete], sender=Genre)
def invalidate_genre_caches(sender, instance, **kwargs):
    """
    Invalidate genre caches when a genre is created, updated, or deleted.

    This is rare (admin-only operation) but important for navigation.

    Affected caches:
    1. All genres list (genre dropdown navigation)
    2. Featured genres list (homepage)
    3. Hierarchical genre structures (NEW)
    4. Flat genre lists (NEW)
    5. Section-specific genre lists (NEW)
    """
    # Delete old cache keys
    cache.delete('genres:all')
    cache.delete('genres:featured')

    # Delete new hierarchical cache keys
    cache.delete('genres:hierarchical:all')
    cache.delete('genres:flat:all')

    # Delete section-specific caches if genre has section
    if instance.section:
        cache.delete(f'genres:hierarchical:section:{instance.section.id}')
        cache.delete(f'genres:flat:section:{instance.section.id}')


@receiver(m2m_changed, sender=BookGenre)
def invalidate_book_genre_caches(sender, instance, action, **kwargs):
    """
    Invalidate caches when book-genre relationships change.

    This handles the many-to-many relationship between books and genres.
    When genres are added or removed from a bookmaster, we need to invalidate
    related book caches.

    Affected caches:
    1. Homepage carousels (if featured books use these genres)
    """
    if action in ['post_add', 'post_remove', 'post_clear']:
        # instance is the BookMaster in this case
        # Invalidate homepage caches for all languages where this book exists
        books = Book.objects.filter(bookmaster=instance)
        for book in books:
            from reader.cache import invalidate_homepage_caches
            invalidate_homepage_caches(book.language.code)


# ==============================================================================
# STATS SIGNALS
# ==============================================================================

@receiver(post_save, sender=ChapterStats)
def invalidate_chapter_stats_caches(sender, instance, **kwargs):
    """
    Invalidate caches when chapter stats are updated.

    This is triggered when Celery tasks aggregate view events into ChapterStats.
    When chapter view counts change, we need to refresh the book's total view count.

    Affected caches:
    1. Total chapter views for the book (aggregated from all chapter stats)
    """
    from reader.cache import invalidate_total_chapter_views

    book = instance.chapter.book
    invalidate_total_chapter_views(book.id)


# ==============================================================================
# SECTION SIGNALS (NEW)
# ==============================================================================

@receiver([post_save, post_delete], sender=Section)
def invalidate_section_caches(sender, instance, **kwargs):
    """
    Invalidate section caches when a section is created, updated, or deleted.

    This is rare (admin-only operation) but important for navigation.

    Affected caches:
    1. All sections list (section navigation)
    2. Public sections list (reader view)
    3. Genre caches (genres are grouped by section)
    """
    cache.delete('sections:all')
    cache.delete('sections:public')

    # Also invalidate genre caches since they're grouped by section
    cache.delete('genres:hierarchical:all')
    cache.delete('genres:flat:all')


# ==============================================================================
# TAG SIGNALS (NEW)
# ==============================================================================

@receiver([post_save, post_delete], sender=Tag)
def invalidate_tag_caches(sender, instance, **kwargs):
    """
    Invalidate tag caches when a tag is created, updated, or deleted.

    This is rare (admin-only operation) but important for tag filtering.

    Affected caches:
    1. All tags list (tag navigation)
    2. Category-specific tag lists
    """
    cache.delete('tags:all')

    # Delete category-specific cache if tag has category
    if instance.category:
        cache.delete(f'tags:category:{instance.category}')


# ==============================================================================
# STYLECONFIG SIGNALS
# ==============================================================================

from reader.models import StyleConfig

@receiver([post_save, post_delete], sender=StyleConfig)
def invalidate_styleconfig_caches(sender, instance, **kwargs):
    """
    Invalidate StyleConfig caches when a style is created, updated, or deleted.

    Affected caches:
    1. Individual style cache for this object
    2. Model-level cache for this content type
    """
    from reader.cache import invalidate_style_config_cache

    invalidate_style_config_cache(instance.content_type_id, instance.object_id)


# ==============================================================================
# AUTHOR SIGNALS
# ==============================================================================

from books.models import Author

@receiver([post_save, post_delete], sender=Author)
def invalidate_author_caches(sender, instance, **kwargs):
    """
    Invalidate Author caches when an author is created, updated, or deleted.

    Affected caches:
    1. Individual author cache by ID
    2. Individual author cache by slug
    3. All authors list
    """
    from reader.cache import invalidate_author_cache

    invalidate_author_cache(author_id=instance.id, slug=instance.slug)
