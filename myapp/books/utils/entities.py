"""
Entity rebuild utilities.

This module provides functions to rebuild entity data from ChapterContext records.
Used when ChapterContext changes (re-analysis, manual edits, chapter deletion).
"""

import logging
from django.db import transaction

from books.models import BookEntity, Chapter
from books.choices import EntityType

logger = logging.getLogger(__name__)


def rebuild_bookmaster_entities(bookmaster):
    """
    Rebuild all entity data for a bookmaster from ChapterContext records.

    This function:
    1. Scans all ChapterContext records for the bookmaster
    2. Collects entity occurrences with first/last chapter info
    3. Creates new entities, updates existing ones, removes orphaned ones

    Use cases:
    - ChapterContext re-analyzed (key_terms changed)
    - Chapter deleted
    - Manual entity cleanup
    - Data migration/repair

    Args:
        bookmaster: BookMaster instance to rebuild entities for

    Returns:
        dict: Summary of changes {created, updated, deleted}
    """
    # Import here to avoid circular imports
    from books.models import ChapterContext

    # Get all chapters ordered by chapter_number
    chapters = Chapter.objects.filter(
        book__bookmaster=bookmaster
    ).select_related(
        'chaptermaster'
    ).order_by('chaptermaster__chapter_number')

    # Build entity occurrence map from ChapterContext
    # Structure: {source_name: {type, first_chapter, last_chapter, count}}
    entity_map = {}

    for chapter in chapters:
        try:
            context = chapter.context
        except ChapterContext.DoesNotExist:
            continue

        entity_mappings = [
            (context.key_terms.get("characters", []), EntityType.CHARACTER),
            (context.key_terms.get("places", []), EntityType.PLACE),
            (context.key_terms.get("terms", []), EntityType.TERM),
        ]

        for entity_list, entity_type in entity_mappings:
            for name in entity_list:
                if name not in entity_map:
                    # First occurrence
                    entity_map[name] = {
                        'entity_type': entity_type,
                        'first_chapter': chapter,
                        'last_chapter': chapter,
                        'occurrence_count': 1,
                    }
                else:
                    # Subsequent occurrence
                    entity_map[name]['last_chapter'] = chapter
                    entity_map[name]['occurrence_count'] += 1

    # Apply changes in a transaction
    stats = {'created': 0, 'updated': 0, 'deleted': 0}

    with transaction.atomic():
        # Get existing entities
        existing_entities = {
            e.source_name: e
            for e in BookEntity.objects.filter(bookmaster=bookmaster)
        }

        # Process entity map
        for source_name, data in entity_map.items():
            if source_name in existing_entities:
                # Update existing entity (preserve translations)
                entity = existing_entities[source_name]
                entity.entity_type = data['entity_type']
                entity.first_chapter = data['first_chapter']
                entity.last_chapter = data['last_chapter']
                entity.occurrence_count = data['occurrence_count']
                entity.save(update_fields=[
                    'entity_type', 'first_chapter', 'last_chapter', 'occurrence_count'
                ])
                stats['updated'] += 1
                del existing_entities[source_name]  # Mark as processed
            else:
                # Create new entity
                BookEntity.objects.create(
                    bookmaster=bookmaster,
                    source_name=source_name,
                    entity_type=data['entity_type'],
                    first_chapter=data['first_chapter'],
                    last_chapter=data['last_chapter'],
                    occurrence_count=data['occurrence_count'],
                    translations={},
                )
                stats['created'] += 1

        # Delete orphaned entities (no longer in any ChapterContext)
        orphaned_names = list(existing_entities.keys())
        if orphaned_names:
            deleted_count, _ = BookEntity.objects.filter(
                bookmaster=bookmaster,
                source_name__in=orphaned_names
            ).delete()
            stats['deleted'] = deleted_count

    logger.info(
        f"Rebuilt entities for '{bookmaster.canonical_title}': "
        f"created={stats['created']}, updated={stats['updated']}, deleted={stats['deleted']}"
    )

    return stats


def rebuild_single_chapter_entities(chapter):
    """
    Convenience function to rebuild entities after a single chapter's context changes.

    This triggers a full bookmaster rebuild since entity first/last chapters
    may shift when any chapter's context changes.

    Args:
        chapter: Chapter instance whose context changed

    Returns:
        dict: Summary of changes {created, updated, deleted}
    """
    if chapter.book and chapter.book.bookmaster:
        return rebuild_bookmaster_entities(chapter.book.bookmaster)
    return {'created': 0, 'updated': 0, 'deleted': 0}
