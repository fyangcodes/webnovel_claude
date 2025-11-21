"""
Signal handlers for BookEntity auto-rebuild.

This module defines signal handlers that automatically rebuild BookEntity
records when ChapterContext is created, updated, or deleted. This ensures
entity occurrence counts and first/last chapter tracking stays in sync.

Signal handlers:
- ChapterContext post_save: Rebuild entities when context is saved
- ChapterContext post_delete: Rebuild entities when context is deleted
"""

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from books.models import ChapterContext
from books.utils.entities import rebuild_single_chapter_entities

import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=ChapterContext)
def rebuild_entities_on_context_save(sender, instance, **kwargs):
    """
    Rebuild entity data when ChapterContext is saved (created or updated).

    This triggers a full bookmaster entity rebuild because:
    - New entities may be introduced
    - Entity occurrence counts need recalculation
    - First/last chapter references may change

    Args:
        sender: The model class (ChapterContext)
        instance: The context instance that was saved
        **kwargs: Additional signal arguments (created, update_fields, etc.)
    """
    try:
        stats = rebuild_single_chapter_entities(instance.chapter)
        logger.debug(
            f"Rebuilt entities after context save for chapter '{instance.chapter.title}': "
            f"created={stats['created']}, updated={stats['updated']}, deleted={stats['deleted']}"
        )
    except Exception as e:
        logger.error(
            f"Failed to rebuild entities after context save for "
            f"chapter '{instance.chapter.title}': {e}",
            exc_info=True
        )


@receiver(post_delete, sender=ChapterContext)
def rebuild_entities_on_context_delete(sender, instance, **kwargs):
    """
    Rebuild entity data when ChapterContext is deleted.

    This triggers a full bookmaster entity rebuild because:
    - Entities may become orphaned (no longer in any chapter)
    - Entity occurrence counts need recalculation
    - First/last chapter references may change

    Args:
        sender: The model class (ChapterContext)
        instance: The context instance that was deleted
        **kwargs: Additional signal arguments
    """
    try:
        stats = rebuild_single_chapter_entities(instance.chapter)
        logger.debug(
            f"Rebuilt entities after context delete for chapter '{instance.chapter.title}': "
            f"created={stats['created']}, updated={stats['updated']}, deleted={stats['deleted']}"
        )
    except Exception as e:
        logger.error(
            f"Failed to rebuild entities after context delete for "
            f"chapter '{instance.chapter.title}': {e}",
            exc_info=True
        )
