"""
Keyword extraction and management utilities.

This module provides functions to extract and manage search keywords from
book taxonomy (sections, genres, tags) and entities (characters, places, terms).
"""

import logging
from typing import List, Dict, Set

from books.models import BookKeyword
from books.choices import KeywordType, EntityType

logger = logging.getLogger(__name__)


def update_book_keywords(bookmaster):
    """
    Rebuild all keywords for a bookmaster from taxonomy, entities, and book metadata.

    This function extracts keywords from:
    - Book titles (canonical and language-specific)
    - Author names (from language-specific books)
    - Section name (if assigned)
    - Genre names (including parent genres)
    - Tag names
    - Entity names (characters, places, terms)

    Keywords are created for each language found in translations, plus the
    primary language name. Different keyword types are weighted differently
    for search ranking.

    Args:
        bookmaster: BookMaster instance to update keywords for

    Returns:
        int: Number of keywords created

    Weights applied:
    - Title: 2.0 (highest - direct title match is most relevant)
    - Author: 1.8 (high - author search is common use case)
    - Section: 1.5 (broad categorization)
    - Genre: 1.0 (standard - primary classification)
    - Tag: 0.8 (moderate - descriptive attributes)
    - Entity: 0.4-1.1 (dynamic - based on occurrence frequency)
    """
    # Delete existing keywords for this bookmaster
    BookKeyword.objects.filter(bookmaster=bookmaster).delete()

    keywords_to_create = []
    seen_keywords = set()  # Track (keyword, language_code, type) to avoid duplicates

    # 1. Extract title keywords (highest weight)
    keywords_to_create.extend(
        _extract_title_keywords(bookmaster, seen_keywords)
    )

    # 2. Extract author keywords (high weight)
    keywords_to_create.extend(
        _extract_author_keywords(bookmaster, seen_keywords)
    )

    # 3. Extract section keywords
    if bookmaster.section:
        keywords_to_create.extend(
            _extract_section_keywords(bookmaster, seen_keywords)
        )

    # 4. Extract genre keywords
    keywords_to_create.extend(
        _extract_genre_keywords(bookmaster, seen_keywords)
    )

    # 5. Extract tag keywords
    keywords_to_create.extend(
        _extract_tag_keywords(bookmaster, seen_keywords)
    )

    # 6. Extract entity keywords (dynamic weight based on occurrence)
    keywords_to_create.extend(
        _extract_entity_keywords(bookmaster, seen_keywords)
    )

    # Bulk create all keywords
    if keywords_to_create:
        BookKeyword.objects.bulk_create(keywords_to_create)
        logger.info(
            f"Created {len(keywords_to_create)} keywords for bookmaster '{bookmaster.canonical_title}'"
        )

    return len(keywords_to_create)


def _extract_title_keywords(bookmaster, seen_keywords: Set) -> List[BookKeyword]:
    """
    Extract keywords from book titles.

    Sources:
    - BookMaster.canonical_title (original language)
    - Book.title for each language version

    Weight: 2.0 (highest - direct title match is most relevant)
    """
    keywords = []
    weight = 2.0

    # Get original language code
    original_lang = bookmaster.original_language.code if bookmaster.original_language else 'zh'

    # Add canonical title (original language)
    _add_keyword(
        keywords, seen_keywords, bookmaster,
        bookmaster.canonical_title, KeywordType.TITLE, original_lang, weight
    )

    # Add titles from all language-specific Book instances
    for book in bookmaster.books.all():
        if book.title:
            _add_keyword(
                keywords, seen_keywords, bookmaster,
                book.title, KeywordType.TITLE, book.language.code, weight
            )

    return keywords


def _extract_author_keywords(bookmaster, seen_keywords: Set) -> List[BookKeyword]:
    """
    Extract keywords from author names.

    Sources:
    - Book.author for each language version

    Weight: 1.8 (high - author search is common use case)
    """
    keywords = []
    weight = 1.8

    # Get author names from all language-specific Book instances
    for book in bookmaster.books.all():
        if book.author:
            _add_keyword(
                keywords, seen_keywords, bookmaster,
                book.author, KeywordType.AUTHOR, book.language.code, weight
            )

    return keywords


def _extract_section_keywords(bookmaster, seen_keywords: Set) -> List[BookKeyword]:
    """
    Extract keywords from section (name + translations).

    Section.name is treated as English (default language) since Section is
    a shared model not tied to any specific bookmaster's original language.
    """
    keywords = []
    section = bookmaster.section
    weight = 1.5

    # Section.name is the default language (English)
    # Sections are shared across all books, so name is not bookmaster-specific
    default_lang = 'en'

    # Add primary section name keyword (in default language)
    _add_keyword(
        keywords, seen_keywords, bookmaster,
        section.name, KeywordType.SECTION, default_lang, weight
    )

    # Add translated section names
    if section.translations:
        for lang_code, translation_data in section.translations.items():
            if isinstance(translation_data, dict) and 'name' in translation_data:
                _add_keyword(
                    keywords, seen_keywords, bookmaster,
                    translation_data['name'], KeywordType.SECTION, lang_code, weight
                )

    return keywords


def _extract_genre_keywords(bookmaster, seen_keywords: Set) -> List[BookKeyword]:
    """
    Extract keywords from genres (name + parent names + translations).

    Genre.name is treated as English (default language) since Genre is
    a shared model not tied to any specific bookmaster's original language.
    """
    keywords = []
    weight = 1.0

    # Genre.name is the default language (English)
    # Genres are shared across all books, so name is not bookmaster-specific
    default_lang = 'en'

    # Get all genres through BookGenre relationship
    book_genres = bookmaster.book_genres.select_related('genre', 'genre__parent').all()

    for book_genre in book_genres:
        genre = book_genre.genre

        # Add primary genre name (in default language)
        _add_keyword(
            keywords, seen_keywords, bookmaster,
            genre.name, KeywordType.GENRE, default_lang, weight
        )

        # Add parent genre name if exists (in default language)
        if genre.parent:
            _add_keyword(
                keywords, seen_keywords, bookmaster,
                genre.parent.name, KeywordType.GENRE, default_lang, weight
            )

        # Add translated genre names
        if genre.translations:
            for lang_code, translation_data in genre.translations.items():
                if isinstance(translation_data, dict) and 'name' in translation_data:
                    _add_keyword(
                        keywords, seen_keywords, bookmaster,
                        translation_data['name'], KeywordType.GENRE, lang_code, weight
                    )

        # Add translated parent genre names if exists
        if genre.parent and genre.parent.translations:
            for lang_code, translation_data in genre.parent.translations.items():
                if isinstance(translation_data, dict) and 'name' in translation_data:
                    _add_keyword(
                        keywords, seen_keywords, bookmaster,
                        translation_data['name'], KeywordType.GENRE, lang_code, weight
                    )

    return keywords


def _extract_tag_keywords(bookmaster, seen_keywords: Set) -> List[BookKeyword]:
    """
    Extract keywords from tags (name + translations).

    Tag.name is treated as English (default language) since Tag is
    a shared model not tied to any specific bookmaster's original language.
    """
    keywords = []
    weight = 0.8

    # Tag.name is the default language (English)
    # Tags are shared across all books, so name is not bookmaster-specific
    default_lang = 'en'

    # Get all tags through BookTag relationship
    book_tags = bookmaster.book_tags.select_related('tag').all()

    for book_tag in book_tags:
        tag = book_tag.tag

        # Add primary tag name (in default language)
        _add_keyword(
            keywords, seen_keywords, bookmaster,
            tag.name, KeywordType.TAG, default_lang, weight
        )

        # Add translated tag names
        if tag.translations:
            for lang_code, translation_data in tag.translations.items():
                if isinstance(translation_data, dict) and 'name' in translation_data:
                    _add_keyword(
                        keywords, seen_keywords, bookmaster,
                        translation_data['name'], KeywordType.TAG, lang_code, weight
                    )

    return keywords


def _calculate_entity_weight(entity, total_chapters: int) -> float:
    """
    Calculate entity keyword weight based on occurrence frequency.

    Weight formula:
    - Base weight: 0.4
    - Frequency bonus: up to 0.6 based on occurrence ratio

    Examples (for a 100-chapter book):
    - Entity in 1 chapter:   0.4 + (1/100 * 0.6)   = 0.406
    - Entity in 10 chapters: 0.4 + (10/100 * 0.6)  = 0.46
    - Entity in 50 chapters: 0.4 + (50/100 * 0.6)  = 0.7
    - Entity in 100 chapters: 0.4 + (100/100 * 0.6) = 1.0

    Additional modifiers:
    - Characters get +0.1 bonus (protagonists are common search terms)
    - Places get +0.05 bonus
    """
    BASE_WEIGHT = 0.4
    MAX_FREQUENCY_BONUS = 0.6

    # Calculate frequency ratio (capped at 1.0)
    if total_chapters > 0:
        occurrence_count = getattr(entity, 'occurrence_count', 1) or 1
        frequency_ratio = min(occurrence_count / total_chapters, 1.0)
    else:
        frequency_ratio = 0.0

    weight = BASE_WEIGHT + (frequency_ratio * MAX_FREQUENCY_BONUS)

    # Entity type bonus
    if entity.entity_type == EntityType.CHARACTER:
        weight += 0.1
    elif entity.entity_type == EntityType.PLACE:
        weight += 0.05

    return min(weight, 1.1)  # Cap at 1.1


def _extract_entity_keywords(bookmaster, seen_keywords: Set) -> List[BookKeyword]:
    """
    Extract keywords from entities with dynamic weights based on occurrence.

    Entities that appear in more chapters get higher weights, making them
    more relevant in search results. Characters and places also get
    type-based bonuses.
    """
    keywords = []

    # Get total chapter count for frequency calculation
    from django.db.models import Count
    total_chapters = bookmaster.books.aggregate(
        total=Count('chapters')
    )['total'] or 1

    # Get original language code
    original_lang = bookmaster.original_language.code if bookmaster.original_language else 'zh'

    # Get all entities for this bookmaster
    entities = bookmaster.entities.all()

    for entity in entities:
        # Calculate dynamic weight based on occurrence
        weight = _calculate_entity_weight(entity, total_chapters)

        # Map EntityType to KeywordType
        keyword_type_map = {
            EntityType.CHARACTER: KeywordType.ENTITY_CHARACTER,
            EntityType.PLACE: KeywordType.ENTITY_PLACE,
            EntityType.TERM: KeywordType.ENTITY_TERM,
        }
        keyword_type = keyword_type_map.get(entity.entity_type, KeywordType.ENTITY_TERM)

        # Add primary entity name (source_name)
        _add_keyword(
            keywords, seen_keywords, bookmaster,
            entity.source_name, keyword_type, original_lang, weight
        )

        # Add translated entity names (same weight)
        if entity.translations:
            for lang_code, translated_name in entity.translations.items():
                if translated_name:  # translations is dict with {lang_code: translated_name}
                    _add_keyword(
                        keywords, seen_keywords, bookmaster,
                        translated_name, keyword_type, lang_code, weight
                    )

    return keywords


def _add_keyword(
    keywords: List[BookKeyword],
    seen_keywords: Set,
    bookmaster,
    keyword: str,
    keyword_type: str,
    language_code: str,
    weight: float
):
    """
    Add a keyword to the list if not already seen.

    Uses seen_keywords set to track (keyword_lower, language_code, keyword_type) tuples
    to prevent duplicates within the same bookmaster.
    """
    if not keyword or not keyword.strip():
        return

    keyword = keyword.strip()
    keyword_lower = keyword.lower()

    # Create unique key for deduplication
    key = (keyword_lower, language_code, keyword_type)

    if key not in seen_keywords:
        seen_keywords.add(key)
        keywords.append(
            BookKeyword(
                bookmaster=bookmaster,
                keyword=keyword,
                keyword_type=keyword_type,
                language_code=language_code,
                weight=weight,
            )
        )
