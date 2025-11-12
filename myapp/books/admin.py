from django.contrib import admin
from background_task import background
from .models import (
    Language,
    Genre,
    BookGenre,
    BookMaster,
    Book,
    ChapterMaster,
    Chapter,
    TranslationJob,
    BookEntity,
    ChapterContext,
    ChapterStats,
    BookStats,
    ViewEvent,
)


@admin.register(Language)
class LanguageAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "local_name", "count_units", "wpm"]
    search_fields = ["name", "code", "local_name"]
    ordering = ["name"]

    fieldsets = (
        (None, {"fields": ("code", "name", "local_name", "count_units", "wpm")}),
        (
            "Count Formatting",
            {
                "fields": ("count_format_rules",),
                "description": 'JSON field for number formatting rules. Example: {"6": "M", "3": "K"} for English or {"8": "亿", "4": "万"} for Chinese. Key is power of 10, value is the suffix.',
                "classes": ("collapse",),
            },
        ),
    )


@admin.register(Genre)
class GenreAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "created_at"]
    search_fields = ["name", "slug"]
    prepopulated_fields = {"slug": ("name",)}
    ordering = ["name"]

    fieldsets = (
        (None, {"fields": ("name", "slug", "description")}),
        (
            "Translations",
            {
                "fields": ("translations",),
                "description": 'JSON field containing localized names and descriptions for different languages, {"zh":{"name":"名称","discription":"描述"}}',
                "classes": ("collapse",),
            },
        ),
    )


class BookGenreInline(admin.TabularInline):
    model = BookGenre
    extra = 1
    fields = ["genre", "order"]
    ordering = ["order"]


class ChapterStatsInline(admin.TabularInline):
    """Inline display of chapter statistics"""

    model = ChapterStats
    fields = [
        "total_views",
        "unique_views_7d",
        "unique_views_30d",
        "completion_count",
        "last_viewed_at",
    ]
    readonly_fields = fields
    can_delete = False
    max_num = 0  # Read-only, no adding new stats
    extra = 0

    def has_add_permission(self, request, obj=None):
        return False


class BookStatsInline(admin.TabularInline):
    """Inline display of book statistics"""

    model = BookStats
    fields = [
        "total_views",
        "unique_readers_7d",
        "unique_readers_30d",
        "last_viewed_at",
    ]
    readonly_fields = fields
    can_delete = False
    max_num = 0  # Read-only
    extra = 0

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(BookMaster)
class BookMasterAdmin(admin.ModelAdmin):
    list_display = [
        "canonical_title",
        "owner",
        "original_language",
        "genre_list",
        "created_at",
    ]
    list_filter = ["original_language", "created_at"]
    search_fields = ["canonical_title"]
    ordering = ["canonical_title"]
    inlines = [BookGenreInline]

    fieldsets = (
        (None, {"fields": ("canonical_title", "owner", "original_language")}),
        (
            "Images",
            {
                "fields": ("cover_image", "hero_image"),
                "description": "Cover image for standard display, Hero image for featured/carousel display",
            },
        ),
    )

    def genre_list(self, obj):
        """Display genres in order"""
        genres = obj.book_genres.select_related("genre").order_by("order")
        return ", ".join([bg.genre.name for bg in genres])

    genre_list.short_description = "Genres"


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = [
        "title",
        "bookmaster",
        "language",
        "is_public",
        "progress",
        "total_chapters",
        "created_at",
    ]
    list_filter = ["is_public", "progress", "language", "created_at"]
    search_fields = ["title", "bookmaster__canonical_title", "author"]
    prepopulated_fields = {"slug": ("title",)}
    readonly_fields = ["total_chapters", "total_words", "total_characters"]
    ordering = ["-created_at"]
    inlines = [BookStatsInline]


@admin.register(ChapterMaster)
class ChapterMasterAdmin(admin.ModelAdmin):
    list_display = ["canonical_title", "bookmaster", "chapter_number", "created_at"]
    list_filter = ["bookmaster", "created_at"]
    search_fields = ["canonical_title", "bookmaster__canonical_title"]
    ordering = ["bookmaster", "chapter_number"]


@admin.register(Chapter)
class ChapterAdmin(admin.ModelAdmin):
    list_display = [
        "title",
        "book",
        "is_public",
        "progress",
        "word_count",
        "scheduled_at",
        "published_at",
        "created_at",
    ]
    list_filter = [
        "is_public",
        "progress",
        "book",
        "scheduled_at",
        "published_at",
        "created_at",
    ]
    search_fields = ["title", "chaptermaster__canonical_title", "book__title"]
    prepopulated_fields = {"slug": ("title",)}
    readonly_fields = ["word_count", "character_count"]
    ordering = ["book", "chaptermaster__chapter_number"]
    inlines = [ChapterStatsInline]


@admin.register(TranslationJob)
class TranslationJobAdmin(admin.ModelAdmin):
    list_display = [
        "chapter",
        "target_language",
        "status",
        "created_by",
        "created_at",
        "updated_at",
    ]
    list_filter = ["status", "target_language", "created_at"]
    search_fields = ["chapter__title", "target_language__name", "created_by__username"]
    readonly_fields = ["created_at", "updated_at"]
    ordering = ["-created_at"]
    actions = ["process_selected_jobs", "process_all_pending_jobs"]

    def process_selected_jobs(self, request, queryset):
        """Queue selected translation jobs for background processing"""
        from books.choices import ProcessingStatus

        pending_jobs = queryset.filter(status=ProcessingStatus.PENDING)
        job_count = pending_jobs.count()

        if job_count == 0:
            self.message_user(request, "No pending jobs selected")
            return

        # Queue each job for background processing
        for job in pending_jobs:
            process_single_job(job.id)

        self.message_user(
            request,
            f"Queued {job_count} translation jobs for background processing. Check back in a few minutes.",
        )

    process_selected_jobs.short_description = "Process selected translation jobs"

    def process_all_pending_jobs(self, request, queryset=None):
        """Queue all pending translation jobs for background processing"""
        from books.choices import ProcessingStatus

        pending_jobs = TranslationJob.objects.filter(status=ProcessingStatus.PENDING)[
            :50
        ]
        job_count = pending_jobs.count()

        if job_count == 0:
            self.message_user(request, "No pending jobs found")
            return

        # Queue jobs for background processing
        for job in pending_jobs:
            process_single_job(job.id)

        self.message_user(
            request,
            f"Queued {job_count} translation jobs for background processing. Check back in a few minutes.",
        )

    process_all_pending_jobs.short_description = "Queue all pending jobs (max 50)"


@admin.register(BookEntity)
class BookEntityAdmin(admin.ModelAdmin):
    list_display = [
        "source_name",
        "entity_type",
        "bookmaster",
        "first_chapter",
        "created_at",
    ]
    list_filter = ["entity_type", "bookmaster", "created_at"]
    search_fields = [
        "source_name",
        "bookmaster__canonical_title",
        "first_chapter__title",
    ]
    readonly_fields = ["created_at", "updated_at"]
    ordering = ["bookmaster", "entity_type", "source_name"]

    fieldsets = (
        (
            None,
            {"fields": ("bookmaster", "entity_type", "source_name", "first_chapter")},
        ),
        (
            "Translations",
            {
                "fields": ("translations",),
                "description": "JSON field containing translations in different languages",
            },
        ),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    def get_queryset(self, request):
        return (
            super().get_queryset(request).select_related("bookmaster", "first_chapter")
        )


@admin.register(ChapterContext)
class ChapterContextAdmin(admin.ModelAdmin):
    list_display = [
        "chapter",
        "entity_count",
        "has_summary",
        "created_at",
        "updated_at",
    ]
    list_filter = ["created_at", "updated_at", "chapter__book"]
    search_fields = ["chapter__title", "chapter__book__title", "summary"]
    readonly_fields = ["created_at", "updated_at", "entity_count"]
    ordering = ["-updated_at"]
    actions = ["extract_entities_for_selected", "clear_analysis"]

    fieldsets = (
        (None, {"fields": ("chapter",)}),
        (
            "Analysis Results",
            {
                "fields": ("key_terms", "summary", "entity_count"),
                "description": "AI-extracted entities and summary",
            },
        ),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    def entity_count(self, obj):
        """Count total entities extracted"""
        if not obj.key_terms:
            return 0
        total = 0
        for category in ["characters", "places", "terms"]:
            if category in obj.key_terms:
                total += len(obj.key_terms[category])
        return total

    entity_count.short_description = "Total entities"

    def has_summary(self, obj):
        """Check if summary exists"""
        return bool(obj.summary)

    has_summary.boolean = True
    has_summary.short_description = "Has summary"

    def extract_entities_for_selected(self, request, queryset):
        """Trigger entity extraction for selected chapters"""
        count = 0
        errors = []

        for context in queryset:
            try:
                context.analyze_with_ai()
                count += 1
            except Exception as e:
                errors.append(f"{context.chapter.title}: {str(e)}")

        if count > 0:
            self.message_user(
                request, f"Successfully extracted entities for {count} chapters"
            )

        if errors:
            self.message_user(
                request,
                f"Errors occurred: {'; '.join(errors[:3])}{'...' if len(errors) > 3 else ''}",
                level="WARNING",
            )

    extract_entities_for_selected.short_description = "Extract entities with AI"

    def clear_analysis(self, request, queryset):
        """Clear analysis data for selected chapters"""
        count = queryset.update(key_terms={}, summary="")
        self.message_user(request, f"Cleared analysis for {count} chapters")

    clear_analysis.short_description = "Clear analysis data"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("chapter", "chapter__book")


@admin.register(ViewEvent)
class ViewEventAdmin(admin.ModelAdmin):
    """Admin interface for viewing statistics events"""

    list_display = [
        "id",
        "content_type",
        "object_id",
        "session_key_short",
        "viewed_at",
        "read_duration",
        "completed",
    ]
    list_filter = ["content_type", "completed", "viewed_at"]
    search_fields = ["session_key", "object_id"]
    readonly_fields = [
        "content_type",
        "object_id",
        "session_key",
        "viewed_at",
        "read_duration_seconds",
        "completed",
        "user_agent",
        "referrer",
        "created_at",
        "updated_at",
    ]
    date_hierarchy = "viewed_at"
    ordering = ["-viewed_at"]

    def session_key_short(self, obj):
        """Display shortened session key"""
        return obj.session_key[:8] + "..." if obj.session_key else "-"

    session_key_short.short_description = "Session"

    def read_duration(self, obj):
        """Display reading duration in human-readable format"""
        if obj.read_duration_seconds:
            minutes = obj.read_duration_seconds // 60
            seconds = obj.read_duration_seconds % 60
            return f"{minutes}m {seconds}s"
        return "-"

    read_duration.short_description = "Duration"

    def has_add_permission(self, request):
        """Prevent manual creation of view events"""
        return False


@background(schedule=0)  # Execute immediately
def process_single_job(job_id):
    """Background task to process a single translation job"""
    from translation.services import TranslationService
    from books.choices import ProcessingStatus
    import logging

    logger = logging.getLogger(__name__)

    try:
        job = TranslationJob.objects.get(id=job_id)

        # Skip if job is no longer pending
        if job.status != ProcessingStatus.PENDING:
            logger.info(f"Job {job_id} is no longer pending, skipping")
            return

        # Mark as processing
        job.status = ProcessingStatus.PROCESSING
        job.save()

        # Process the translation
        service = TranslationService()
        service.translate_chapter(job.chapter, job.target_language.code)

        # Mark as completed
        job.status = ProcessingStatus.COMPLETED
        job.error_message = ""
        job.save()

        logger.info(f"Successfully processed translation job {job_id}")

    except TranslationJob.DoesNotExist:
        logger.error(f"Translation job {job_id} not found")
    except Exception as e:
        logger.error(f"Error processing translation job {job_id}: {str(e)}")
        try:
            job = TranslationJob.objects.get(id=job_id)
            job.status = ProcessingStatus.FAILED
            job.error_message = str(e)
            job.save()
        except TranslationJob.DoesNotExist:
            pass
