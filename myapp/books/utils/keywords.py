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
    Rebuild all keywords for a bookmaster from taxonomy and entities.

    This function extracts keywords from:
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
    - Section: 1.5 (highest - broad categorization)
    - Genre: 1.0 (standard - primary classification)
    - Tag: 0.8 (moderate - descriptive attributes)
    - Entity: 0.6 (lower - specific names, may not be search terms)
    """
    # Delete existing keywords for this bookmaster
    BookKeyword.objects.filter(bookmaster=bookmaster).delete()

    keywords_to_create = []
    seen_keywords = set()  # Track (keyword, language_code, type) to avoid duplicates

    # 1. Extract section keywords
    if bookmaster.section:
        keywords_to_create.extend(
            _extract_section_keywords(bookmaster, seen_keywords)
        )

    # 2. Extract genre keywords
    keywords_to_create.extend(
        _extract_genre_keywords(bookmaster, seen_keywords)
    )

    # 3. Extract tag keywords
    keywords_to_create.extend(
        _extract_tag_keywords(bookmaster, seen_keywords)
    )

    # 4. Extract entity keywords
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


def _extract_entity_keywords(bookmaster, seen_keywords: Set) -> List[BookKeyword]:
    """Extract keywords from entities (characters, places, terms)"""
    keywords = []
    weight = 0.6

    # Get original language code
    original_lang = bookmaster.original_language.code if bookmaster.original_language else 'zh'

    # Get all entities for this bookmaster
    entities = bookmaster.entities.all()

    for entity in entities:
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

        # Add translated entity names
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
