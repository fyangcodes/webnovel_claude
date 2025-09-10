from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.text import slugify

from common.models import TimeStampedModel
from .choices import BookProgress, ChapterProgress, ProcessingStatus, CountUnits
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

        # Use atomic transaction to prevent race conditions
        with transaction.atomic():
            # Try numbered suffixes first (more user-friendly)
            for counter in range(1, 100):
                candidate_slug = f"{base_slug}-{counter}"
                if (
                    not model_class.objects.filter(slug=candidate_slug, **filter_kwargs)
                    .exclude(pk=self.pk)
                    .exists()
                ):
                    return candidate_slug
            else:
                # Fallback to UUID if too many conflicts
                return f"{base_slug}-{uuid.uuid4().hex[:8]}"


class Language(TimeStampedModel):
    code = models.CharField(max_length=10, unique=True)  # e.g., 'zh-CN'
    name = models.CharField(max_length=50)  # e.g., 'Chinese (Simplified)'
    local_name = models.CharField(max_length=50)  # e.g., '中文（简体）'
    count_units = models.CharField(
        max_length=20,
        choices=CountUnits.choices,
        default=CountUnits.WORDS,
    )
    wpm = models.PositiveSmallIntegerField(
        default=400, help_text="Reading speed words per minute"
    )

    def __str__(self):
        return self.name


class BookMaster(TimeStampedModel):
    """Master book entity for translation management"""

    canonical_title = models.CharField(max_length=255)
    cover_image = models.ImageField(
        upload_to="book_covers/masters/",
        blank=True,
        null=True,
        help_text="Default cover image for all language versions of this book",
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

    class Meta:
        ordering = ["canonical_title"]
        indexes = [
            models.Index(fields=["canonical_title"]),
            models.Index(fields=["owner"]),
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
        BookMaster, on_delete=models.CASCADE, related_name="books"
    )
    language = models.ForeignKey(
        Language, on_delete=models.SET_NULL, null=True, blank=True
    )
    is_public = models.BooleanField(
        default=False, help_text="Whether this book is visible to readers"
    )
    progress = models.CharField(
        max_length=20,
        choices=BookProgress.choices,
        default=BookProgress.DRAFT,
    )
    published_at = models.DateTimeField(null=True, blank=True)

    # Simple metadata
    total_chapters = models.PositiveIntegerField(default=0)
    total_words = models.PositiveIntegerField(default=0)  # for space seperated language
    total_characters = models.PositiveIntegerField(default=0)  # for non-space-seperated

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
        if self.language.count_units == CountUnits.WORDS:
            return self.total_words
        return self.total_characters

    @property
    def reading_time_minutes(self):
        """Calculate estimated reading time for the entire book in minutes"""
        if not self.language or not self.language.wpm:
            return 0

        effective_count = self.effective_count
        if effective_count == 0:
            return 0

        # Convert to minutes, rounding up to nearest minute
        import math

        return math.ceil(effective_count / self.language.wpm)

    @property
    def effective_cover_image(self):
        if self.cover_image:
            return self.cover_image.url
        elif self.bookmaster.cover_image:
            return self.bookmaster.cover_image.url
        else:
            from django.templatetags.static import static

            return static("books/images/default_book_cover.png")


class ChapterMaster(TimeStampedModel):
    """Master chapter entity"""

    canonical_title = models.CharField(max_length=255)
    bookmaster = models.ForeignKey(
        BookMaster, on_delete=models.CASCADE, related_name="chaptermasters"
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
        max_length=255, blank=True, validators=[unicode_slug_validator]
    )
    chaptermaster = models.ForeignKey(
        ChapterMaster, on_delete=models.CASCADE, related_name="chapters"
    )
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="chapters")

    # Simple content storage
    content = models.TextField(help_text="Chapter content as plain text")
    excerpt = models.TextField(max_length=1000, blank=True)
    word_count = models.PositiveIntegerField(default=0)
    character_count = models.PositiveIntegerField(default=0)

    # Simple publishing
    is_public = models.BooleanField(
        default=False, help_text="Whether this chapter is visible to readers"
    )
    progress = models.CharField(
        max_length=20,
        choices=ChapterProgress.choices,
        default=ChapterProgress.DRAFT,
    )
    scheduled_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this chapter should be automatically published",
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
        return f"{self.title} ({self.chaptermaster.canonical_title})"

    def save(self, *args, **kwargs):
        base_slug = slugify(self.title, allow_unicode=True)
        self.slug = self.generate_unique_slug(base_slug, {"book": self.book})
        # Update word count
        if self.content:
            self.word_count = len(self.content.split())
            self.character_count = len(self.content)
            self.generate_excerpt()
        super().save(*args, **kwargs)

    def generate_excerpt(self, max_length=200):
        """Generate excerpt from content"""
        if not self.content:
            self.excerpt = ""
        elif len(self.content) <= max_length:
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
        if self.book.language.count_units == CountUnits.WORDS:
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

    chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE)
    target_language = models.ForeignKey(Language, on_delete=models.CASCADE)
    status = models.CharField(
        max_length=20,
        choices=ProcessingStatus.choices,
        default=ProcessingStatus.PENDING,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True
    )
    error_message = models.TextField(blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"Translation of {self.chapter.title} to {self.target_language.name}"
