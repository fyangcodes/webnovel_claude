from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.text import slugify

from common.models import TimeStampedModel
from .choices import (
    BookProgress,
    ChapterProgress,
    ProcessingStatus,
    CountUnit,
    EntityType,
)
from .validators import unicode_slug_validator


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
    hero_image=models.ImageField(
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
            return self.effective_cover_image()


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

        # Track if this is a new chapter or content changed
        is_new = self.pk is None
        content_changed = False
        if not is_new:
            # Check if content changed by comparing with database
            try:
                old_chapter = Chapter.objects.get(pk=self.pk)
                content_changed = old_chapter.content != self.content
            except Chapter.DoesNotExist:
                content_changed = True

        super().save(*args, **kwargs)

        # Auto-trigger entity extraction for original language chapters
        if (
            (is_new or content_changed)
            and self.content
            and self.book.language == self.book.bookmaster.original_language
        ):
            self._trigger_entity_extraction()

    def _trigger_entity_extraction(self):
        """Trigger entity extraction for this chapter"""
        try:
            context, created = ChapterContext.objects.get_or_create(chapter=self)
            # Only extract if not already done or content is empty
            if created or not context.key_terms:
                context.analyze_chapter()
        except Exception as e:
            # Log error but don't break the save process
            import logging

            logger = logging.getLogger("books")
            logger.error(
                f"Failed to trigger entity extraction for chapter {self.id}: {e}"
            )

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


# Simple translation job tracking
class TranslationJob(TimeStampedModel):
    """Simple job tracking for async translations"""

    chapter = models.ForeignKey(
        Chapter,
        on_delete=models.CASCADE,
    )
    target_language = models.ForeignKey(
        Language,
        on_delete=models.CASCADE,
    )
    status = models.CharField(
        max_length=20,
        choices=ProcessingStatus.choices,
        default=ProcessingStatus.PENDING,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
    )
    error_message = models.TextField(blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"Translation of {self.chapter.title} (#{self.chapter.pk}) to {self.target_language.name}"


class BookEntity(TimeStampedModel):

    bookmaster = models.ForeignKey(
        BookMaster,
        on_delete=models.CASCADE,
        related_name="entities",
    )
    entity_type = models.CharField(
        max_length=20,
        choices=EntityType.choices,
    )
    source_name = models.CharField(max_length=255)
    translations = models.JSONField(default=dict, blank=True)  # {"en": "Li Wei", "es": "Li Wei"}
    first_chapter = models.ForeignKey(
        Chapter,
        on_delete=models.CASCADE,
        related_name="entities",
    )

    class Meta:
        unique_together = ["bookmaster", "source_name"]
        indexes = [
            models.Index(fields=["bookmaster", "entity_type"]),
        ]

    def get_translation(self, language_code):
        return self.translations.get(language_code)

    def set_translation(self, language_code, translated_name):
        self.translations[language_code] = translated_name
        self.save(update_fields=["translations"])


class ChapterContext(TimeStampedModel):
    """Chapter context and entity analysis for translation consistency"""

    chapter = models.OneToOneField(
        Chapter,
        on_delete=models.CASCADE,
        related_name="context",
    )
    key_terms = models.JSONField(
        default=dict
    )  # {"characters": [], "places": [], "terms": []}
    summary = models.TextField(blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["chapter"]),
        ]

    def __str__(self):
        return f"Context for {self.chapter.title} ({self.chapter.book.title})"

    def analyze_chapter(self):
        """Use AI to extract entities and summary from chapter content"""
        from translation.services import EntityExtractionService

        try:
            extractor = EntityExtractionService()
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


class ChapterStats(TimeStampedModel):
    """Statistics for individual chapters (session-based anonymous tracking)"""

    chapter = models.OneToOneField(
        Chapter,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="stats",
    )

    # View counts
    total_views = models.BigIntegerField(
        default=0,
        help_text="Total number of views (all time)",
    )
    unique_views_24h = models.IntegerField(
        default=0,
        help_text="Unique sessions in last 24 hours",
    )
    unique_views_7d = models.IntegerField(
        default=0,
        help_text="Unique sessions in last 7 days",
    )
    unique_views_30d = models.IntegerField(
        default=0,
        help_text="Unique sessions in last 30 days",
    )
    unique_views_all_time = models.IntegerField(
        default=0,
        help_text="Unique sessions (all time)",
    )

    # Engagement metrics
    total_read_time_seconds = models.BigIntegerField(
        default=0,
        help_text="Total time spent reading this chapter (seconds)",
    )
    completion_count = models.IntegerField(
        default=0,
        help_text="Number of times readers reached the end",
    )

    # Metadata
    last_viewed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last time this chapter was viewed",
    )

    class Meta:
        verbose_name_plural = "Chapter stats"
        indexes = [
            models.Index(fields=["total_views"]),
            models.Index(fields=["unique_views_7d"]),
            models.Index(fields=["last_viewed_at"]),
        ]

    def __str__(self):
        return f"Stats for {self.chapter.title} ({self.total_views} views)"

    @property
    def average_read_time_seconds(self):
        """Calculate average reading time"""
        if self.total_views == 0:
            return 0
        return self.total_read_time_seconds // self.total_views

    @property
    def completion_rate(self):
        """Calculate percentage of readers who completed the chapter"""
        if self.total_views == 0:
            return 0
        return (self.completion_count / self.total_views) * 100


class BookStats(TimeStampedModel):
    """Statistics for books (session-based anonymous tracking)"""

    book = models.OneToOneField(
        Book,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="stats",
    )

    # View counts
    total_views = models.BigIntegerField(
        default=0,
        help_text="Total number of views (all time)",
    )
    unique_readers_24h = models.IntegerField(
        default=0,
        help_text="Unique sessions in last 24 hours",
    )
    unique_readers_7d = models.IntegerField(
        default=0,
        help_text="Unique sessions in last 7 days",
    )
    unique_readers_30d = models.IntegerField(
        default=0,
        help_text="Unique sessions in last 30 days",
    )
    unique_readers_all_time = models.IntegerField(
        default=0,
        help_text="Unique sessions (all time)",
    )

    # Engagement metrics
    total_read_time_seconds = models.BigIntegerField(
        default=0,
        help_text="Total time spent on this book (seconds)",
    )

    # Metadata
    last_viewed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last time this book was viewed",
    )

    class Meta:
        verbose_name_plural = "Book stats"
        indexes = [
            models.Index(fields=["total_views"]),
            models.Index(fields=["unique_readers_7d"]),
            models.Index(fields=["last_viewed_at"]),
        ]

    def __str__(self):
        return f"Stats for {self.book.title} ({self.total_views} views)"

    @property
    def average_read_time_seconds(self):
        """Calculate average reading time"""
        if self.total_views == 0:
            return 0
        return self.total_read_time_seconds // self.total_views

    def get_total_chapter_views(self, include_realtime=True):
        """
        Calculate total views across all published chapters of this book.

        Args:
            include_realtime: Include pending Redis counts (default: True)

        Returns:
            int: Sum of total_views from all published chapters' ChapterStats
        """
        from django.db.models import Sum

        # Get all published chapters for this book
        published_chapters = self.book.chapters.filter(is_public=True)

        # Aggregate total views from ChapterStats (PostgreSQL)
        result = ChapterStats.objects.filter(
            chapter__in=published_chapters
        ).aggregate(total=Sum('total_views'))

        total_views = result['total'] or 0

        # Add real-time Redis counts (not yet aggregated to PostgreSQL)
        if include_realtime:
            try:
                from .stats import StatsService
                redis_client = StatsService._get_redis_client()

                if redis_client:
                    for chapter in published_chapters:
                        redis_key = f"{StatsService.REDIS_PREFIX}:chapter:{chapter.id}:views"
                        redis_views = redis_client.get(redis_key)
                        if redis_views:
                            total_views += int(redis_views)
            except Exception:
                # Silently fail if Redis is unavailable
                pass

        return total_views


class ViewEvent(TimeStampedModel):
    """
    Time-series event log for detailed analytics.
    Records individual view events using session-based anonymous tracking.
    Privacy-friendly: uses Django session IDs, no personal data.
    """

    # What was viewed (generic foreign key)
    content_type = models.ForeignKey(
        "contenttypes.ContentType",
        on_delete=models.CASCADE,
    )
    object_id = models.PositiveIntegerField()
    # Note: GenericForeignKey is added via property, not database field

    # Who viewed it (anonymous session tracking)
    session_key = models.CharField(
        max_length=40,
        help_text="Django session ID for anonymous user tracking",
    )

    # When was it viewed
    viewed_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When this view occurred",
    )

    # Engagement metrics (updated by JavaScript)
    read_duration_seconds = models.IntegerField(
        null=True,
        blank=True,
        help_text="Time spent reading (updated by JavaScript)",
    )
    completed = models.BooleanField(
        default=False,
        help_text="Whether user scrolled to end of content",
    )

    # Context (optional, for analytics)
    user_agent = models.TextField(
        null=True,
        blank=True,
        help_text="Browser/device information",
    )
    referrer = models.URLField(
        null=True,
        blank=True,
        max_length=500,
        help_text="Previous page URL (traffic source)",
    )

    class Meta:
        ordering = ["-viewed_at"]
        indexes = [
            # For queries like "all views of Chapter 123 in last 7 days"
            models.Index(fields=["content_type", "object_id", "viewed_at"]),
            # For time-range queries
            models.Index(fields=["viewed_at"]),
            # For user journey tracking
            models.Index(fields=["session_key", "viewed_at"]),
        ]

    def __str__(self):
        return f"{self.content_type} #{self.object_id} viewed at {self.viewed_at}"

    @property
    def content_object(self):
        """Get the actual object that was viewed"""
        from django.contrib.contenttypes.models import ContentType

        ct = ContentType.objects.get_for_id(self.content_type_id)
        return ct.get_object_for_this_type(pk=self.object_id)
