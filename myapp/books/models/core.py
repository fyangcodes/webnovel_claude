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
from django.utils import timezone
from django.utils.text import slugify

from common.models import TimeStampedModel
from books.choices import BookProgress, ChapterProgress, CountUnit
from books.validators import unicode_slug_validator


class SlugGeneratorMixin:
    """Mixin to generate unique slugs with automatic conflict resolution"""

    def generate_unique_slug(self, base_slug, filter_kwargs=None):
        from django.db import transaction
        import uuid

        filter_kwargs = filter_kwargs or {}
        model_class = self.__class__

        # Try the base slug first
        if (
            not model_class.objects.filter(slug=base_slug, **filter_kwargs)
            .exclude(pk=self.pk)
            .exists()
        ):
            return base_slug
        # If not, include uuid in slug
        return f"{base_slug}-{uuid.uuid4().hex[:8]}"


class Language(TimeStampedModel):
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
        help_text="Number formatting rules. Example: {6: 'M', 3: 'K'} for English, {8: '亿', 4: '万'} for Chinese"
    )
    # count_format_rules format:
    # Key: power of 10 (6 = million, 3 = thousand, 4 = 10k, 8 = 100M)
    # Value: suffix string ('M', 'K', '万', '亿')
    # Rules are applied in descending order of power

    def __str__(self):
        return self.name


class Genre(TimeStampedModel):
    """Genre/category for books"""

    name = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    translations = models.JSONField(default=dict, blank=True)
    # translations = {
    #     "zh": {"name": "修仙", "description": "修仙小说..."},
    #     "en": {"name": "Xianxia", "description": "Cultivation novels..."}
    # }

    def __str__(self):
        return f"{self.name}"

    def save(self, *args, **kwargs):
        self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_localized_name(self, language_code):
        if language_code in self.translations:
            return self.translations[language_code].get("name", self.name)
        return self.name

    def get_localized_description(self, language_code):
        if language_code in self.translations:
            return self.translations[language_code].get("description", self.description)
        return self.description


class BookGenre(TimeStampedModel):
    """Through model for ordered book-genre relationship"""

    bookmaster = models.ForeignKey(
        "BookMaster",
        on_delete=models.CASCADE,
        related_name="book_genres",
    )
    genre = models.ForeignKey(
        "Genre",
        on_delete=models.CASCADE,
        related_name="book_genres",
    )
    order = models.PositiveSmallIntegerField(
        default=0, help_text="Display order for this genre (lower = first)"
    )

    class Meta:
        ordering = ["order", "id"]
        unique_together = ["bookmaster", "genre"]
        indexes = [
            models.Index(fields=["bookmaster", "order"]),
        ]

    def __str__(self):
        return f"{self.bookmaster.canonical_title} - {self.genre.name} (order: {self.order})"


class BookMaster(TimeStampedModel):
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
    genres = models.ManyToManyField(
        "Genre",
        through="BookGenre",
        related_name="bookmasters",
        blank=True,
        help_text="Book genres/categories",
    )

    class Meta:
        ordering = ["-created_at"]
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
        super().save(*args, **kwargs)

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


class Book(TimeStampedModel, SlugGeneratorMixin):
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

    class Meta:
        ordering = ["-created_at"]
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


class ChapterMaster(TimeStampedModel):
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
        indexes = [
            models.Index(fields=["canonical_title"]),
            models.Index(fields=["bookmaster"]),
            models.Index(fields=["chapter_number"]),
        ]

    def __str__(self):
        return self.canonical_title


class Chapter(TimeStampedModel, SlugGeneratorMixin):
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
