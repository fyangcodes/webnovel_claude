"""
Signal handlers for BookKeyword auto-population.

This module defines signal handlers that automatically populate and update
BookKeyword records when taxonomy (sections, genres, tags) or entities are
created, updated, or deleted. This ensures the search index stays in sync
with the book's metadata.

Signal handlers:
- BookMaster post_save: Update section keywords when section is assigned
- Book post_save: Update title/author keywords when book is created/updated
- BookGenre m2m_changed: Update genre keywords when genres are added/removed
- BookTag m2m_changed: Update tag keywords when tags are added/removed
- BookEntity post_save: Update entity keywords when entities are created/updated
"""

from django.db.models.signals import post_save, m2m_changed
from django.dispatch import receiver

from books.models import Book, BookMaster, BookGenre, BookTag, BookEntity
from books.utils import update_book_keywords

import logging

logger = logging.getLogger(__name__)


# ==============================================================================
# BOOKMASTER SIGNALS
# ==============================================================================

@receiver(post_save, sender=BookMaster)
def update_bookmaster_keywords(sender, instance, **kwargs):
    """
    Update keywords when BookMaster is saved.

    This primarily handles section keyword updates when a section is assigned
    or changed. It also ensures keywords are created for new bookmasters.

    Args:
        sender: The model class (BookMaster)
        instance: The bookmaster instance that was saved
        **kwargs: Additional signal arguments (created, update_fields, etc.)
    """
    try:
        # Update all keywords for this bookmaster
        # This includes section, genres, tags, and entities
        keyword_count = update_book_keywords(instance)
        logger.debug(
            f"Updated {keyword_count} keywords for bookmaster '{instance.canonical_title}'"
        )
    except Exception as e:
        logger.error(
            f"Failed to update keywords for bookmaster '{instance.canonical_title}': {e}",
            exc_info=True
        )


# ==============================================================================
# BOOK SIGNALS
# ==============================================================================

@receiver(post_save, sender=Book)
def update_book_title_author_keywords(sender, instance, **kwargs):
    """
    Update keywords when Book is saved.

    This handles title and author keyword updates when a Book (language-specific
    version) is created or updated. Updates the keywords for the bookmaster
    to include this book's title and author.

    Args:
        sender: The model class (Book)
        instance: The book instance that was saved
        **kwargs: Additional signal arguments (created, update_fields, etc.)
    """
    if not instance.bookmaster:
        return

    try:
        # Update all keywords for the bookmaster this book belongs to
        keyword_count = update_book_keywords(instance.bookmaster)
        logger.debug(
            f"Updated {keyword_count} keywords after book change "
            f"(title: {instance.title}) for "
            f"bookmaster '{instance.bookmaster.canonical_title}'"
        )
    except Exception as e:
        logger.error(
            f"Failed to update keywords after book change "
            f"(title: {instance.title}): {e}",
            exc_info=True
        )


# ==============================================================================
# GENRE SIGNALS
# ==============================================================================

@receiver(m2m_changed, sender=BookGenre)
def update_genre_keywords(sender, instance, action, **kwargs):
    """
    Update genre keywords when BookGenre relationships change.

    This handles the many-to-many relationship between bookmasters and genres.
    When genres are added or removed from a bookmaster, we need to update
    the genre keywords in the search index.

    Args:
        sender: The through model (BookGenre)
        instance: The bookmaster instance
        action: The M2M action (pre_add, post_add, pre_remove, post_remove, etc.)
        **kwargs: Additional signal arguments (pk_set, etc.)
    """
    # Only update after changes are committed to database
    if action in ['post_add', 'post_remove', 'post_clear']:
        try:
            # Update all keywords for this bookmaster
            keyword_count = update_book_keywords(instance)
            logger.debug(
                f"Updated {keyword_count} keywords after genre change for "
                f"bookmaster '{instance.canonical_title}'"
            )
        except Exception as e:
            logger.error(
                f"Failed to update keywords after genre change for "
                f"bookmaster '{instance.canonical_title}': {e}",
                exc_info=True
            )


# ==============================================================================
# TAG SIGNALS
# ==============================================================================

@receiver(m2m_changed, sender=BookTag)
def update_tag_keywords(sender, instance, action, **kwargs):
    """
    Update tag keywords when BookTag relationships change.

    This handles the many-to-many relationship between bookmasters and tags.
    When tags are added or removed from a bookmaster, we need to update
    the tag keywords in the search index.

    Args:
        sender: The through model (BookTag)
        instance: The bookmaster instance
        action: The M2M action (pre_add, post_add, pre_remove, post_remove, etc.)
        **kwargs: Additional signal arguments (pk_set, etc.)
    """
    # Only update after changes are committed to database
    if action in ['post_add', 'post_remove', 'post_clear']:
        try:
            # Update all keywords for this bookmaster
            keyword_count = update_book_keywords(instance)
            logger.debug(
                f"Updated {keyword_count} keywords after tag change for "
                f"bookmaster '{instance.canonical_title}'"
            )
        except Exception as e:
            logger.error(
                f"Failed to update keywords after tag change for "
                f"bookmaster '{instance.canonical_title}': {e}",
                exc_info=True
            )


# ==============================================================================
# ENTITY SIGNALS
# ==============================================================================

@receiver(post_save, sender=BookEntity)
def update_entity_keywords(sender, instance, **kwargs):
    """
    Update entity keywords when BookEntity is saved.

    This handles character, place, and term entities. When an entity is
    created or updated, we need to update the entity keywords for the
    bookmaster.

    Args:
        sender: The model class (BookEntity)
        instance: The entity instance that was saved
        **kwargs: Additional signal arguments (created, update_fields, etc.)
    """
    try:
        # Update all keywords for the bookmaster this entity belongs to
        bookmaster = instance.bookmaster
        keyword_count = update_book_keywords(bookmaster)
        logger.debug(
            f"Updated {keyword_count} keywords after entity change "
            f"({instance.entity_type}: {instance.source_name}) for "
            f"bookmaster '{bookmaster.canonical_title}'"
        )
    except Exception as e:
        logger.error(
            f"Failed to update keywords after entity change "
            f"({instance.entity_type}: {instance.source_name}): {e}",
            exc_info=True
        )
