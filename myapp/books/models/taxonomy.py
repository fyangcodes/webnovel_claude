"""
Taxonomy and classification models for content organization.

This module contains models for categorizing and tagging books:
- Section: Top-level content categories (Fiction, BL, GL, Non-fiction)
- Genre: Hierarchical genre system (primary and sub-genres)
- BookGenre: Through model for ordered book-genre relationships
- Tag: Flexible tagging system for book attributes
- BookTag: Through model for book-tag relationships
- BookKeyword: Denormalized search index for fast keyword lookups
"""

from django.conf import settings
from django.db import models
from django.core.exceptions import ValidationError
from django.utils.text import slugify

from books.models.base import TimeStampedModel
from books.choices import TagCategory, TagSource, KeywordType


class Section(TimeStampedModel):
    """
    Top-level content category for books.

    Sections represent fundamentally different content types that may require
    different moderation, age-gating, or browsing experiences.
    Examples: Fiction, BL (Boys' Love), GL (Girls' Love), Non-fiction
    """

    name = models.CharField(
        max_length=50,
        unique=True,
        help_text="Section name (e.g., 'Fiction', 'BL', 'GL')"
    )
    slug = models.SlugField(
        max_length=50,
        unique=True,
        help_text="URL-friendly identifier"
    )
    description = models.TextField(
        blank=True,
        help_text="Description of this section"
    )
    order = models.PositiveSmallIntegerField(
        default=0,
        help_text="Display order (lower = first)"
    )
    is_mature = models.BooleanField(
        default=False,
        help_text="Whether this section contains mature content requiring age verification"
    )
    translations = models.JSONField(
        default=dict,
        blank=True,
        help_text="Localized names and descriptions. Format: {language_code: {name, description}}"
    )

    class Meta:
        ordering = ['order', 'name']
        verbose_name = "Section"
        verbose_name_plural = "Taxonomy - Sections"
        indexes = [
            models.Index(fields=['order']),
            models.Index(fields=['slug']),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_localized_name(self, language_code):
        """Get localized section name or fall back to default"""
        if language_code in self.translations:
            return self.translations[language_code].get('name', self.name)
        return self.name

    def get_localized_description(self, language_code):
        """Get localized section description or fall back to default"""
        if language_code in self.translations:
            return self.translations[language_code].get('description', self.description)
        return self.description


class Genre(TimeStampedModel):
    """
    Hierarchical genre classification system.

    Genres are organized within sections and can be:
    - Primary genres (is_primary=True, parent=None): Main categories for browsing
    - Sub-genres (is_primary=False, parent=<primary>): Refinements of primary genres

    Note: Genre names can repeat across sections (e.g., "Romance" in both Fiction and BL),
    enforced by unique_together on (section, slug).
    """

    section = models.ForeignKey(
        Section,
        on_delete=models.CASCADE,
        related_name='genres',
        null=True,  # Temporarily nullable for migration
        blank=True,
        help_text="The section this genre belongs to"
    )
    name = models.CharField(
        max_length=50,
        help_text="Genre name (can repeat across sections)"
    )
    slug = models.SlugField(
        max_length=50,
        help_text="URL-friendly identifier (unique within section)"
    )
    description = models.TextField(
        blank=True,
        help_text="Description of this genre"
    )
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='sub_genres',
        help_text="Parent genre (only for sub-genres)"
    )
    is_primary = models.BooleanField(
        default=True,
        help_text="Primary genres appear in main navigation; sub-genres are refinements"
    )
    translations = models.JSONField(
        default=dict,
        blank=True,
        help_text="Localized names and descriptions. Format: {language_code: {name, description}}"
    )

    class Meta:
        ordering = ['section', '-is_primary', 'name']
        verbose_name = "Genre"
        verbose_name_plural = "Taxonomy - Genres"
        unique_together = [['section', 'slug']]
        indexes = [
            models.Index(fields=['section', 'is_primary']),
            models.Index(fields=['section', 'slug']),
            models.Index(fields=['parent']),
        ]

    def __str__(self):
        if not self.section:
            return self.name
        if self.parent:
            return f"{self.section.name} > {self.parent.name} > {self.name}"
        return f"{self.section.name} > {self.name}"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        # Call clean() to validate before saving
        self.full_clean()
        super().save(*args, **kwargs)

    def clean(self):
        """Validate genre hierarchy rules"""
        super().clean()

        # Rule 1: Primary genres cannot have parents
        if self.is_primary and self.parent:
            raise ValidationError({
                'parent': "Primary genres cannot have a parent genre. Set is_primary=False for sub-genres."
            })

        # Rule 2: Sub-genres must have a primary parent
        if not self.is_primary:
            if not self.parent:
                raise ValidationError({
                    'parent': "Sub-genres must have a parent genre."
                })
            if not self.parent.is_primary:
                raise ValidationError({
                    'parent': "Sub-genres must have a primary genre as parent (no nested sub-genres)."
                })

        # Rule 3: Parent must be in the same section
        if self.parent and self.section and self.parent.section != self.section:
            raise ValidationError({
                'parent': f"Parent genre must belong to the same section ({self.section.name})."
            })

        # Rule 4: Self-reference check (genre cannot be its own parent)
        if self.parent and self.pk and self.parent.pk == self.pk:
            raise ValidationError({
                'parent': "A genre cannot be its own parent."
            })

        # Rule 5: Circular reference check (prevent A -> B -> A)
        if self.parent and self.parent.parent and self.pk:
            if self.parent.parent.pk == self.pk:
                raise ValidationError({
                    'parent': f"Circular reference detected: {self.name} -> {self.parent.name} -> "
                              f"{self.parent.parent.name} creates a loop back to {self.name}."
                })

    def get_localized_name(self, language_code):
        """Get localized genre name or fall back to default"""
        if language_code in self.translations:
            return self.translations[language_code].get('name', self.name)
        return self.name

    def get_localized_description(self, language_code):
        """Get localized genre description or fall back to default"""
        if language_code in self.translations:
            return self.translations[language_code].get('description', self.description)
        return self.description


class BookGenre(TimeStampedModel):
    """
    Through model for ordered book-genre relationships.

    Allows books to have multiple genres with specific display ordering.
    The order field determines the sequence in which genres appear in the UI.
    """

    bookmaster = models.ForeignKey(
        'BookMaster',
        on_delete=models.CASCADE,
        related_name='book_genres',
    )
    genre = models.ForeignKey(
        Genre,
        on_delete=models.CASCADE,
        related_name='book_genres',
    )
    order = models.PositiveSmallIntegerField(
        default=0,
        help_text="Display order for this genre (lower = first)"
    )

    class Meta:
        ordering = ['order', 'id']
        unique_together = [['bookmaster', 'genre']]
        indexes = [
            models.Index(fields=['bookmaster', 'order']),
        ]

    def __str__(self):
        return f"{self.bookmaster.canonical_title} - {self.genre.name} (order: {self.order})"

    def clean(self):
        """Validate that genre belongs to bookmaster's section"""
        super().clean()

        if self.bookmaster.section and self.genre.section != self.bookmaster.section:
            raise ValidationError({
                'genre': f"Genre must belong to the book's section ({self.bookmaster.section.name})."
            })


class Tag(TimeStampedModel):
    """
    Flexible tagging system for book attributes.

    Tags provide fine-grained metadata about books, such as:
    - Protagonist type (female-lead, male-lead)
    - Narrative style (first-person, third-person)
    - Themes (revenge, redemption)
    - Tropes (system, transmigration, regression)
    - Content warnings (violence, sexual content)
    """

    name = models.CharField(
        max_length=50,
        unique=True,
        help_text="Tag name (e.g., 'Female Lead', 'System')"
    )
    slug = models.SlugField(
        max_length=50,
        unique=True,
        help_text="URL-friendly identifier"
    )
    category = models.CharField(
        max_length=20,
        choices=TagCategory.choices,
        help_text="Category for organizing tags"
    )
    description = models.TextField(
        blank=True,
        help_text="Description of this tag"
    )
    translations = models.JSONField(
        default=dict,
        blank=True,
        help_text="Localized names and descriptions. Format: {language_code: {name, description}}"
    )

    class Meta:
        ordering = ['category', 'name']
        verbose_name = "Tag"
        verbose_name_plural = "Taxonomy - Tags"
        indexes = [
            models.Index(fields=['category']),
            models.Index(fields=['slug']),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_category_display()})"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_localized_name(self, language_code):
        """Get localized tag name or fall back to default"""
        if language_code in self.translations:
            return self.translations[language_code].get('name', self.name)
        return self.name

    def get_localized_description(self, language_code):
        """Get localized tag description or fall back to default"""
        if language_code in self.translations:
            return self.translations[language_code].get('description', self.description)
        return self.description


class BookTag(TimeStampedModel):
    """
    Through model for book-tag relationships with metadata.

    Tracks the source of tag assignment and confidence level for AI-suggested tags.
    """

    bookmaster = models.ForeignKey(
        'BookMaster',
        on_delete=models.CASCADE,
        related_name='book_tags',
    )
    tag = models.ForeignKey(
        Tag,
        on_delete=models.CASCADE,
        related_name='book_tags',
    )
    confidence = models.FloatField(
        default=1.0,
        help_text="Confidence score for AI-suggested tags (0.0-1.0)"
    )
    source = models.CharField(
        max_length=20,
        choices=TagSource.choices,
        default=TagSource.MANUAL,
        help_text="Source of this tag assignment"
    )

    class Meta:
        unique_together = [['bookmaster', 'tag']]
        indexes = [
            models.Index(fields=['bookmaster', 'source']),
            models.Index(fields=['tag']),
        ]

    def __str__(self):
        return f"{self.bookmaster.canonical_title} - {self.tag.name} ({self.get_source_display()})"


class BookKeyword(TimeStampedModel):
    """
    Denormalized keyword index for fast multi-language search.

    This table stores all searchable keywords extracted from:
    - Section names
    - Genre names (primary and sub-genres)
    - Tags
    - Entities (characters, places, terms)

    Enables fast keyword search across all taxonomies without complex joins.
    """

    bookmaster = models.ForeignKey(
        'BookMaster',
        on_delete=models.CASCADE,
        related_name='keywords',
    )
    keyword = models.CharField(
        max_length=255,
        db_index=True,
        help_text="The searchable keyword"
    )
    keyword_type = models.CharField(
        max_length=20,
        choices=KeywordType.choices,
        help_text="Type of keyword for filtering"
    )
    language_code = models.CharField(
        max_length=10,
        help_text="Language of this keyword"
    )
    weight = models.FloatField(
        default=1.0,
        help_text="Relevance weight for ranking (higher = more relevant)"
    )

    class Meta:
        verbose_name = "Book Keyword"
        verbose_name_plural = "Taxonomy - Keywords"
        indexes = [
            models.Index(fields=['keyword', 'keyword_type']),
            models.Index(fields=['bookmaster', 'keyword_type']),
            models.Index(fields=['language_code', 'keyword']),
        ]

    def __str__(self):
        return f"{self.bookmaster.canonical_title} - {self.keyword} ({self.get_keyword_type_display()})"
