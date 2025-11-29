"""
Core content models for the books app.

This module contains the primary content hierarchy:
- Language: Language configuration for internationalization
- Genre: Book genre/category system
- BookGenre: Through model for book-genre relationships
- BookMaster: Master book entity for translation management
- Book: Language-specific book versions
- ChapterMaster: Master chapter entity
- Chapter: Language-specific chapter content
"""

from django.conf import settings
from django.db import models
from django.db.models import Prefetch
from django.utils import timezone
from django.utils.text import slugify

from books.models.base import TimeStampModel, SlugGeneratorMixin
from books.choices import BookProgress, ChapterProgress, CountUnit
from books.validators import unicode_slug_validator


class Language(TimeStampModel):
    code = models.CharField(max_length=10, unique=True)  # e.g., 'zh-CN'
    name = models.CharField(max_length=50)  # e.g., 'Chinese (Simplified)'
    local_name = models.CharField(max_length=50)  # e.g., '中文（简体）'
    count_units = models.CharField(
        max_length=20,
        choices=CountUnit.choices,
        default=CountUnit.WORDS,
    )
    wpm = models.PositiveSmallIntegerField(default=400, help_text="Reading speed")
    count_format_rules = models.JSONField(
        default=dict,
        blank=True,
        help_text="Number formatting rules. Example: {6: 'M', 3: 'K'} for English, {8: '亿', 4: '万'} for Chinese",
    )
    # count_format_rules format:
    # Key: power of 10 (6 = million, 3 = thousand, 4 = 10k, 8 = 100M)
    # Value: suffix string ('M', 'K', '万', '亿')
    # Rules are applied in descending order of power
    is_public = models.BooleanField(
        default=True,
        help_text="Whether this language is visible to readers in the reader app",
    )

    class Meta:
        ordering = ["code"]  # Alphabetical order by language code (de, en, fr, ja, zh)
        verbose_name = "Language"
        verbose_name_plural = "Core - Languages"
        indexes = [
            models.Index(fields=["is_public"]),
            models.Index(fields=["code"]),
        ]

    def __str__(self):
        return self.name


class BookMaster(TimeStampModel):
    """Master book entity for translation management"""

    canonical_title = models.CharField(max_length=255)
    cover_image = models.ImageField(
        upload_to="book_covers/masters/",
        blank=True,
        null=True,
        help_text="Default cover image for all language versions",
    )
    hero_image = models.ImageField(
        upload_to="book_covers/masters/",
        blank=True,
        null=True,
        help_text="Hero image for promotion",
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="books",
        null=True,
        blank=True,
    )
    original_language = models.ForeignKey(
        Language,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="original_books",
    )
    section = models.ForeignKey(
        "Section",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bookmasters",
        help_text="Content section (Fiction, BL, GL, etc.)",
    )
    genres = models.ManyToManyField(
        "Genre",
        through="BookGenre",
        related_name="bookmasters",
        blank=True,
        help_text="Book genres/categories",
    )
    tags = models.ManyToManyField(
        "Tag",
        through="BookTag",
        related_name="bookmasters",
        blank=True,
        help_text="Book tags (protagonist type, tropes, themes, etc.)",
    )
    author = models.ForeignKey(
        "Author",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bookmasters",
        help_text="Original author of the work",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Book Master"
        verbose_name_plural = "Core - Book Masters"
        indexes = [
            models.Index(fields=["canonical_title"]),
            models.Index(fields=["owner"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"{self.canonical_title}"

    def save(self, *args, **kwargs):
        if not self.original_language:
            self.original_language = Language.objects.get(code="zh")
        # Call clean() to validate before saving (only for existing instances)
        if self.pk:
            self.full_clean()
        super().save(*args, **kwargs)

    def clean(self):
        """Validate taxonomy consistency"""
        from django.core.exceptions import ValidationError

        super().clean()

        # Validate that all assigned genres belong to the same section
        if self.pk and self.section:
            mismatched_genres = self.book_genres.exclude(genre__section=self.section)
            if mismatched_genres.exists():
                # Get genre names for helpful error message
                genre_names = ", ".join(
                    bg.genre.name
                    for bg in mismatched_genres.select_related("genre")[:3]
                )
                count = mismatched_genres.count()
                if count > 3:
                    genre_names += f" and {count - 3} more"

                raise ValidationError(
                    {
                        "section": f"Cannot change section to '{self.section.name}' because "
                        f"the following genres belong to different sections: {genre_names}. "
                        f"Remove incompatible genres first or keep the current section."
                    }
                )

    def validate_genres(self):
        """
        Validate genre assignments (called manually or in admin).

        Returns warnings as a list of strings (non-blocking).
        """
        warnings = []

        # Only validate if instance has been saved
        if not self.pk:
            return warnings

        # Check if BookMaster has at least one genre
        if not self.book_genres.exists():
            warnings.append(
                "Book has no genres assigned. Consider adding at least one genre for better discoverability."
            )
        else:
            # Check if BookMaster has at least one primary genre
            primary_genres = self.book_genres.filter(genre__is_primary=True)
            if not primary_genres.exists():
                warnings.append(
                    "Book has no primary genres (only sub-genres). Consider adding a primary genre."
                )

        return warnings

    @property
    def effective_cover_image(self):
        if self.cover_image:
            return self.cover_image.url
        else:
            from django.templatetags.static import static

            return static("books/images/default_book_cover.png")

    @property
    def effective_hero_image(self):
        if self.hero_image:
            return self.hero_image.url
        else:
            return self.effective_cover_image


class BookQuerySet(models.QuerySet):
    """
    Optimized querysets for Book model.

    Key optimizations:
    1. Prefetch objects with select_related (collapses 3 queries → 1)
    2. OneToOne stats with select_related (not prefetch_related)
    3. Reusable prefetch methods (DRY principle)
    4. Context-specific querysets (card vs detail)
    5. Memory optimization with only()
    """

    # ==================================================================
    # PRIVATE HELPER METHODS - Reusable prefetch configurations
    # ==================================================================

    def _prefetch_genres_optimized(self):
        """
        Optimized genre prefetch using Prefetch + select_related.

        Collapses 3 queries into 1:
        - bookmaster__genres
        - bookmaster__genres__section
        - bookmaster__genres__parent

        Returns:
            Prefetch: Optimized genre prefetch object
        """
        from books.models import Genre

        return Prefetch(
            "bookmaster__genres",
            queryset=Genre.objects.select_related(
                "section",  # ← Collapses __section query
                "parent",  # ← Collapses __parent query
            )
            # No need to specify ordering - it will use Genre model's default ordering
            # ordering = ['section', '-is_primary', 'order', 'name']
        )

    def _prefetch_tags_optimized(self):
        """
        Optimized tag prefetch with only() to reduce memory.

        Tags typically only need: id, name, slug, category for display.

        Returns:
            Prefetch: Optimized tag prefetch object
        """
        from books.models import Tag

        return Prefetch(
            "bookmaster__tags",
            queryset=Tag.objects.only(
                "id",
                "name",
                "slug",
                "category",
                "translations",  # For localization
            ),
        )

    def _prefetch_entities_optimized(self):
        """
        Optimized entity prefetch with only() to reduce memory.

        Entities typically only need: id, source_name, translations, entity_type, order.

        Returns:
            Prefetch: Optimized entity prefetch object
        """
        from books.models import BookEntity

        return Prefetch(
            "bookmaster__entities",
            queryset=BookEntity.objects.filter(
                # Exclude default order (999) as per enrichment logic
                ~models.Q(order=999)
            ).only(
                "id",
                "bookmaster_id",
                "source_name",
                "translations",
                "entity_type",
                "order",
            ),
        )

    def _prefetch_chapters_with_stats(self):
        """
        Optimized chapter prefetch with stats select_related.

        IMPORTANT: ChapterStats is OneToOneField with related_name="stats"
        So we use select_related("stats"), not prefetch_related("chapterstats_set")

        Returns:
            Prefetch: Optimized chapter+stats prefetch object
        """
        return Prefetch(
            "chapters",
            queryset=Chapter.objects.select_related(
                "stats",  # ← OneToOne relationship
                "chaptermaster",  # ← Commonly accessed
            ).only(
                # Limit fields to reduce memory
                "id",
                "book_id",
                "chaptermaster_id",
                "slug",
                "is_public",
                "published_at",
                "word_count",
                "character_count",
            ),
        )

    def _select_base_relations(self):
        """
        Base select_related for all book querysets.

        These are OneToOne or ForeignKey relations that should
        ALWAYS be joined in a single query.

        Returns:
            QuerySet: Self with base relations selected
        """
        return self.select_related(
            "bookmaster",
            "bookmaster__section",
            "bookmaster__author",
            "language",
            "stats",  # ← OneToOne relationship (related_name="stats")
        )

    # ==================================================================
    # PUBLIC API - Context-specific querysets
    # ==================================================================

    def with_card_relations(self):
        """
        Lightweight prefetch for book cards (homepage, lists).

        Use this for:
        - Homepage carousels (featured, recent, new)
        - Section home recent books
        - Book list pages
        - Search results

        Does NOT include:
        - chapters (too heavy for list views)
        - chapter stats (not needed for cards)

        Query count: ~5 queries for any number of books
        - 1 for books
        - 1 for genres (with section + parent)
        - 1 for tags
        - 1 for entities
        - 1 for bookstats (already in select_related)

        Returns:
            QuerySet: Optimized for card display
        """
        return self._select_base_relations().prefetch_related(
            self._prefetch_genres_optimized(),
            self._prefetch_tags_optimized(),
            self._prefetch_entities_optimized(),
        )

    def with_full_relations(self):
        """
        Full prefetch including chapters (for detail-adjacent views).

        Use this for:
        - Views that need chapter data but not full detail
        - Author book lists (might show chapter counts)
        - Advanced search with chapter filtering

        Query count: ~6-7 queries for any number of books
        - 5 from with_card_relations()
        - 1-2 for chapters (with stats and chaptermaster)

        Returns:
            QuerySet: Full relations prefetched
        """
        return self.with_card_relations().prefetch_related(
            self._prefetch_chapters_with_stats(),
        )

    def for_list_display(self, language, section=None):
        """
        Optimized queryset for list views with language/section filter.

        Use this for:
        - SectionHomeView
        - SectionBookListView
        - Search results

        This is the RECOMMENDED queryset for most list views.

        Args:
            language: Language object
            section: Section object or None

        Returns:
            QuerySet: Filtered and optimized for list display
        """
        qs = self.filter(language=language, is_public=True)
        if section:
            qs = qs.filter(bookmaster__section=section)
        return qs.with_card_relations()

    def for_detail_display(self, language, slug, section=None):
        """
        Optimized queryset for book detail views.

        Use this for:
        - SectionBookDetailView
        - BookDetailView (legacy)

        Does NOT prefetch chapters because:
        - Chapters use pagination (handled separately in view)
        - Chapter list queries are isolated

        Args:
            language: Language object
            slug: Book slug
            section: Section object or None

        Returns:
            QuerySet: Optimized for detail display
        """
        qs = self.filter(language=language, slug=slug, is_public=True)
        if section:
            qs = qs.filter(bookmaster__section=section)

        # Use card relations (no chapters)
        # Chapters are handled separately with pagination in the view
        return qs.with_card_relations()


class BookManager(models.Manager):
    """
    Custom manager for Book model with optimized querysets.

    Usage:
        # In books/models/core.py, add to Book model:
        objects = BookManager()

        # Then use in views:
        books = Book.objects.for_list_display(language, section)
        book = Book.objects.for_detail_display(language, slug, section).first()
    """

    def get_queryset(self):
        """Return custom BookQuerySet"""
        return BookQuerySet(self.model, using=self._db)

    def with_card_relations(self):
        """Shortcut for with_card_relations()"""
        return self.get_queryset().with_card_relations()

    def with_full_relations(self):
        """Shortcut for with_full_relations()"""
        return self.get_queryset().with_full_relations()

    def for_list_display(self, language, section=None):
        """Shortcut for for_list_display()"""
        return self.get_queryset().for_list_display(language, section)

    def for_detail_display(self, language, slug, section=None):
        """Shortcut for for_detail_display()"""
        return self.get_queryset().for_detail_display(language, slug, section)


class Book(TimeStampModel, SlugGeneratorMixin):
    """Language-specific version of a book"""

    title = models.CharField(max_length=255)
    slug = models.CharField(
        max_length=255,
        unique=True,
        blank=True,
        validators=[unicode_slug_validator],
    )
    author = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    cover_image = models.ImageField(
        upload_to="book_covers/books",
        blank=True,
        null=True,
        help_text="Cover image for the book",
    )
    bookmaster = models.ForeignKey(
        BookMaster,
        on_delete=models.CASCADE,
        related_name="books",
    )
    language = models.ForeignKey(
        Language,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="books",
    )
    is_public = models.BooleanField(
        default=False,
        help_text="Whether visible to readers",
    )
    progress = models.CharField(
        max_length=20,
        choices=BookProgress.choices,
        default=BookProgress.DRAFT,
    )
    published_at = models.DateTimeField(null=True, blank=True)

    # Simple metadata
    total_chapters = models.PositiveIntegerField(default=0)
    total_words = models.PositiveIntegerField(default=0)  # for space seperated text
    total_characters = models.PositiveIntegerField(
        default=0
    )  # for non-space-seperated text

    # NOTE: Custom manager will be assigned after BookManager class is defined below
    # Using default manager for now - will be replaced at end of file
    objects = BookManager()

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Book"
        verbose_name_plural = "Core - Books"
        indexes = [
            models.Index(fields=["created_at"]),
            models.Index(fields=["language", "is_public"]),
            models.Index(fields=["is_public", "progress"]),
        ]

    def __str__(self):
        return f"{self.title} ({self.bookmaster.canonical_title})"

    def save(self, *args, **kwargs):
        base_slug = slugify(self.title, allow_unicode=True)
        self.slug = self.generate_unique_slug(base_slug)

        super().save(*args, **kwargs)

    def update_metadata(self):
        """Update book metadata based on chapters"""
        chapters = self.chapters.all()
        self.total_chapters = chapters.count()
        self.total_words = sum(chapter.word_count for chapter in chapters)
        self.total_characters = sum(chapter.character_count for chapter in chapters)
        self.save(update_fields=["total_chapters", "total_words", "total_characters"])

    @property
    def effective_count(self):
        if self.language.count_units == CountUnit.WORDS:
            return self.total_words
        return self.total_characters

    @property
    def reading_time_minutes(self):
        """Calculate estimated reading time for the entire book in minutes"""
        if not self.language or not self.language.wpm:
            return 0

        if self.effective_count == 0:
            return 0
        # Convert to minutes, rounding up to nearest minute
        import math

        return math.ceil(self.effective_count / self.language.wpm)

    @property
    def effective_cover_image(self):
        if self.cover_image:
            return self.cover_image.url
        return self.bookmaster.effective_cover_image


class ChapterMaster(TimeStampModel):
    """Master chapter entity"""

    canonical_title = models.CharField(max_length=255)
    bookmaster = models.ForeignKey(
        BookMaster,
        on_delete=models.CASCADE,
        related_name="chaptermasters",
    )
    chapter_number = models.PositiveIntegerField()

    class Meta:
        ordering = ["chapter_number"]
        verbose_name = "Chapter Master"
        verbose_name_plural = "Core - Chapter Masters"
        indexes = [
            models.Index(fields=["canonical_title"]),
            models.Index(fields=["bookmaster"]),
            models.Index(fields=["chapter_number"]),
        ]

    def __str__(self):
        return self.canonical_title


class Chapter(TimeStampModel, SlugGeneratorMixin):
    """Simplified chapter with basic text content"""

    title = models.CharField(max_length=255)
    slug = models.CharField(
        max_length=255,
        blank=True,
        validators=[unicode_slug_validator],
    )
    chaptermaster = models.ForeignKey(
        ChapterMaster,
        on_delete=models.CASCADE,
        related_name="chapters",
    )
    book = models.ForeignKey(
        Book,
        on_delete=models.CASCADE,
        related_name="chapters",
    )

    # Simple content storage
    content = models.TextField(help_text="Chapter content")
    excerpt = models.TextField(
        max_length=1000,
        blank=True,
    )
    translator_notes = models.TextField(
        blank=True,
        help_text="Notes about assumptions, clarifications, or challenges",
    )
    word_count = models.PositiveIntegerField(default=0)
    character_count = models.PositiveIntegerField(default=0)

    # Simple publishing
    is_public = models.BooleanField(
        default=False,
        help_text="Whether visible to readers",
    )
    progress = models.CharField(
        max_length=20,
        choices=ChapterProgress.choices,
        default=ChapterProgress.DRAFT,
    )
    scheduled_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When to publish this chapter automatically",
    )
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = [["book", "slug"]]
        verbose_name = "Chapter"
        verbose_name_plural = "Core - Chapters"
        indexes = [
            models.Index(fields=["book", "is_public"]),
            models.Index(fields=["is_public", "progress"]),
            models.Index(fields=["published_at", "is_public"]),
            models.Index(fields=["scheduled_at"]),
        ]

    def __str__(self):
        return f"{self.title} ({self.chaptermaster.bookmaster.canonical_title} > {self.chaptermaster.canonical_title})"

    def save(self, *args, **kwargs):
        base_slug = slugify(self.title, allow_unicode=True)
        self.slug = self.generate_unique_slug(base_slug, {"book": self.book})

        # Update Metadata and excerpt
        if self.content:
            self.update_metadata()
            self.generate_excerpt()

        super().save(*args, **kwargs)

    def update_metadata(self):
        self.word_count = len(self.content.split())
        self.character_count = len(self.content)

    def generate_excerpt(self, max_length=200):
        """Generate excerpt from content"""
        if len(self.content) <= max_length:
            self.excerpt = self.content
        else:
            self.excerpt = self.content[:max_length].rsplit(None, 1)[0] + "..."

    def publish(self):
        """Publish this chapter"""
        self.is_public = True
        self.published_at = timezone.now()
        self.save()

    def unpublish(self):
        """Unpublish this chapter"""
        self.is_public = False
        self.published_at = None
        self.save()

    @property
    def effective_count(self):
        if self.book.language.count_units == CountUnit.WORDS:
            return self.word_count
        return self.character_count

    @property
    def reading_time_minutes(self):
        """Calculate estimated reading time in minutes based on language reading speed"""
        if not self.book.language or not self.book.language.wpm:
            return 0

        effective_count = self.effective_count
        if effective_count == 0:
            return 0

        # Convert to minutes, rounding up to nearest minute
        import math

        return math.ceil(effective_count / self.book.language.wpm)
