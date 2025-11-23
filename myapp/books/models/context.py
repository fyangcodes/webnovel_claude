"""
Context and entity models for AI-powered translation.

This module contains models for storing AI-extracted metadata:
- BookEntity: Named entities (characters, places, terms) from books
- ChapterContext: AI-extracted chapter analysis and summaries
"""

from django.db import models

from books.models.base import TimeStampModel
from books.choices import EntityType


class BookEntity(TimeStampModel):
    """
    Named entity (character, place, term) extracted from a book.

    Tracks where entities first and last appear, and how often they
    occur across chapters for search relevance weighting.
    """

    bookmaster = models.ForeignKey(
        "BookMaster",
        on_delete=models.CASCADE,
        related_name="entities",
    )
    entity_type = models.CharField(
        max_length=20,
        choices=EntityType.choices,
    )
    source_name = models.CharField(max_length=255)
    translations = models.JSONField(default=dict, blank=True)  # {"en": "Li Wei", "es": "Li Wei"}

    # Display order for entity badges
    order = models.PositiveSmallIntegerField(
        default=999,
        help_text="Display order (lower numbers appear first)"
    )

    # Chapter where entity first appears
    first_chapter = models.ForeignKey(
        "Chapter",
        on_delete=models.CASCADE,
        related_name="new_entities",  # Entities introduced in this chapter
        help_text="Chapter where entity first appears",
    )

    # Occurrence tracking for search relevance
    occurrence_count = models.PositiveIntegerField(
        default=1,
        help_text="Number of chapters this entity appears in",
    )
    last_chapter = models.ForeignKey(
        "Chapter",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="latest_entities",  # Entities last seen in this chapter
        help_text="Most recent chapter where entity appears",
    )

    class Meta:
        ordering = ['order', 'source_name']
        unique_together = ["bookmaster", "source_name"]
        verbose_name = "Book Entity"
        verbose_name_plural = "Context - Book Entities"
        indexes = [
            models.Index(fields=["bookmaster", "entity_type"]),
            models.Index(fields=["occurrence_count"]),
            models.Index(fields=["order"]),
        ]

    def get_translation(self, language_code):
        return self.translations.get(language_code)

    def set_translation(self, language_code, translated_name):
        self.translations[language_code] = translated_name
        self.save(update_fields=["translations"])


class ChapterContext(TimeStampModel):
    """Chapter context and entity analysis for translation consistency"""

    chapter = models.OneToOneField(
        "Chapter",
        on_delete=models.CASCADE,
        related_name="context",
    )
    key_terms = models.JSONField(
        default=dict
    )  # {"characters": [], "places": [], "terms": []}
    summary = models.TextField(blank=True)

    class Meta:
        verbose_name = "Chapter Context"
        verbose_name_plural = "Context - Chapter Contexts"
        indexes = [
            models.Index(fields=["chapter"]),
        ]

    def __str__(self):
        return f"Context for {self.chapter.title} ({self.chapter.book.title})"

    def analyze_chapter(self):
        """Use AI to extract entities and summary from chapter content"""
        from books.utils import ChapterAnalysisService

        try:
            extractor = ChapterAnalysisService()
            result = extractor.extract_entities_and_summary(
                self.chapter.content,
                self.chapter.book.language.code if self.chapter.book.language else "zh",
            )

            # Store structured data
            self.summary = result["summary"]
            self.key_terms = {
                "characters": result["characters"],
                "places": result["places"],
                "terms": result["terms"],
            }
            self.save()

            # Create BookEntity records
            self._create_book_entities()

            return result

        except Exception as e:
            import logging

            logger = logging.getLogger("books")
            logger.error(f"Failed to analyze chapter {self.chapter.id} with AI: {e}")
            return self._get_fallback_analysis()

    def _create_book_entities(self):
        """Create BookEntity records from stored key_terms"""
        entity_mappings = [
            (self.key_terms.get("characters", []), EntityType.CHARACTER),
            (self.key_terms.get("places", []), EntityType.PLACE),
            (self.key_terms.get("terms", []), EntityType.TERM),
        ]

        entities = []
        for entity_list, entity_type in entity_mappings:
            for name in entity_list:
                entity, created = BookEntity.objects.get_or_create(
                    bookmaster=self.chapter.book.bookmaster,
                    source_name=name,
                    defaults={
                        "entity_type": entity_type,
                        "first_chapter": self.chapter,
                        "translations": {},
                    },
                )
                entities.append(entity)

        return entities

    def _get_fallback_analysis(self):
        """Return fallback analysis when AI extraction fails"""
        content = self.chapter.content
        return {
            "characters": [],
            "places": [],
            "terms": [],
            "summary": (
                "FALLBACK" + content[:200] + "..." if len(content) > 200 else content
            ),
        }
