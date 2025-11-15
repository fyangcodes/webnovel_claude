from django.contrib import admin
from .models import (
    # Core
    Language,
    BookMaster,
    Book,
    ChapterMaster,
    Chapter,
    # Taxonomy
    Section,
    Genre,
    BookGenre,
    Tag,
    BookTag,
    BookKeyword,
    # Jobs
    TranslationJob,
    AnalysisJob,
    FileUploadJob,
    # Context
    BookEntity,
    ChapterContext,
    # Stats
    ChapterStats,
    BookStats,
    ViewEvent,
)


@admin.register(Language)
class LanguageAdmin(admin.ModelAdmin):
    list_display = ["code", "name", "local_name", "is_public"]
    list_filter = ["is_public"]
    search_fields = ["name", "code", "local_name"]
    readonly_fields = ["pk"]
    ordering = ["code"]  # Order by language code alphabetically (de, en, fr, ja, zh)

    fieldsets = (
        (None, {"fields": ("pk", "code", "name", "local_name", "count_units", "wpm")}),
        (
            "Visibility",
            {
                "fields": ("is_public",),
                "description": "Controls whether this language is visible to readers in the reader app. Staff users can always access private languages.",
            },
        ),
        (
            "Count Formatting",
            {
                "fields": ("count_format_rules",),
                "description": 'JSON field for number formatting rules. Example: {"6": "M", "3": "K"} for English or {"8": "亿", "4": "万"} for Chinese. Key is power of 10, value is the suffix.',
                "classes": ("collapse",),
            },
        ),
    )


# ============================================================================
# TAXONOMY ADMINS
# ============================================================================

@admin.register(Section)
class SectionAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "order", "is_mature", "created_at"]
    list_editable = ["order", "is_mature"]
    list_filter = ["is_mature"]
    search_fields = ["name", "slug"]
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ["pk", "created_at", "updated_at"]
    ordering = ["order", "name"]

    fieldsets = (
        (None, {
            "fields": ("pk", "name", "slug", "description", "icon", "order", "is_mature")
        }),
        (
            "Translations",
            {
                "fields": ("translations",),
                "description": 'JSON field for localized names and descriptions. Format: {"zh": {"name": "小说", "description": "..."}, "en": {...}}',
                "classes": ("collapse",),
            },
        ),
        (
            "Timestamps",
            {
                "fields": ("created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )


@admin.register(Genre)
class GenreAdmin(admin.ModelAdmin):
    list_display = ["name", "section", "parent", "is_primary", "slug", "created_at"]
    list_filter = ["section", "is_primary", "parent"]
    search_fields = ["name", "slug"]
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ["pk", "created_at", "updated_at"]
    ordering = ["section", "-is_primary", "name"]

    fieldsets = (
        (None, {
            "fields": ("pk", "section", "name", "slug", "description", "parent", "is_primary")
        }),
        (
            "Display Options",
            {
                "fields": ("icon", "color"),
                "description": "Visual customization for genre badges and navigation",
            },
        ),
        (
            "Translations",
            {
                "fields": ("translations",),
                "description": 'JSON field for localized names and descriptions. Format: {"zh": {"name": "修仙", "description": "..."}, "en": {...}}',
                "classes": ("collapse",),
            },
        ),
        (
            "Timestamps",
            {
                "fields": ("created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Filter parent choices to same section and primary genres only"""
        if db_field.name == "parent":
            # If editing existing genre, filter by its section
            if request.resolver_match.kwargs.get('object_id'):
                try:
                    genre_id = request.resolver_match.kwargs['object_id']
                    genre = Genre.objects.get(pk=genre_id)
                    kwargs["queryset"] = Genre.objects.filter(
                        section=genre.section,
                        is_primary=True
                    )
                except Genre.DoesNotExist:
                    pass
            # For new genres, show all primary genres (will be filtered by section in JS)
            else:
                kwargs["queryset"] = Genre.objects.filter(is_primary=True)

        if db_field.name == "section":
            kwargs["queryset"] = Section.objects.order_by('order', 'name')

        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ["name", "category", "slug", "created_at"]
    list_filter = ["category"]
    search_fields = ["name", "slug"]
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ["pk", "created_at", "updated_at"]
    ordering = ["category", "name"]

    # Enable autocomplete in BookTagInline
    def get_search_results(self, request, queryset, search_term):
        """Improve autocomplete search"""
        queryset, use_distinct = super().get_search_results(request, queryset, search_term)
        return queryset, use_distinct

    fieldsets = (
        (None, {
            "fields": ("pk", "name", "slug", "category", "description")
        }),
        (
            "Translations",
            {
                "fields": ("translations",),
                "description": 'JSON field for localized tag names and descriptions. Format: {"zh": {"name": "女主", "description": "..."}, "en": {...}}',
                "classes": ("collapse",),
            },
        ),
        (
            "Timestamps",
            {
                "fields": ("created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )


class BookTagInline(admin.TabularInline):
    """Inline for managing book tags"""
    model = BookTag
    extra = 1
    fields = ["tag", "confidence", "source"]
    autocomplete_fields = ["tag"]

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Order tags by category for better UX"""
        if db_field.name == "tag":
            kwargs["queryset"] = Tag.objects.order_by('category', 'name')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(BookKeyword)
class BookKeywordAdmin(admin.ModelAdmin):
    """Admin for search keyword index (mostly read-only)"""
    list_display = ["keyword", "bookmaster", "keyword_type", "language_code", "weight"]
    list_filter = ["keyword_type", "language_code"]
    search_fields = ["keyword", "bookmaster__canonical_title"]
    readonly_fields = ["pk", "created_at", "updated_at"]
    ordering = ["keyword"]

    fieldsets = (
        (None, {
            "fields": ("pk", "bookmaster", "keyword", "keyword_type", "language_code", "weight")
        }),
        (
            "Timestamps",
            {
                "fields": ("created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    def has_add_permission(self, request):
        """Keywords should be auto-generated, not manually added"""
        return False


# ============================================================================
# CORE CONTENT ADMINS
# ============================================================================


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
        "section",
        "owner",
        "original_language",
        "genre_list",
        "tag_list",
        "created_at",
    ]
    list_filter = ["section", "original_language", "created_at"]
    search_fields = ["canonical_title"]
    readonly_fields = ["pk"]
    ordering = ["canonical_title"]
    inlines = [BookGenreInline, BookTagInline]

    fieldsets = (
        (None, {
            "fields": ("pk", "canonical_title", "section", "owner", "original_language")
        }),
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

    def tag_list(self, obj):
        """Display tags"""
        tags = obj.book_tags.select_related("tag").all()[:5]
        tag_names = [bt.tag.name for bt in tags]
        if obj.book_tags.count() > 5:
            tag_names.append(f"... +{obj.book_tags.count() - 5} more")
        return ", ".join(tag_names) if tag_names else "-"

    tag_list.short_description = "Tags"


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
    readonly_fields = ["pk", "total_chapters", "total_words", "total_characters"]
    ordering = ["-created_at"]
    inlines = [BookStatsInline]


@admin.register(ChapterMaster)
class ChapterMasterAdmin(admin.ModelAdmin):
    list_display = ["canonical_title", "bookmaster", "chapter_number", "created_at"]
    list_filter = ["bookmaster", "created_at"]
    search_fields = ["canonical_title", "bookmaster__canonical_title"]
    readonly_fields = ["pk"]
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
    readonly_fields = ["pk", "word_count", "character_count"]
    ordering = ["book", "chaptermaster__chapter_number"]
    inlines = [ChapterStatsInline]


# ============================================================================
# JOB/TASK ADMINS
# ============================================================================


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
    readonly_fields = ["pk", "created_at", "updated_at"]
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

        # Trigger Celery task to process translation jobs
        from books.tasks.chapter_translation import process_translation_jobs
        process_translation_jobs.delay(max_jobs=job_count)

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

        # Trigger Celery task to process translation jobs
        from books.tasks.chapter_translation import process_translation_jobs
        process_translation_jobs.delay(max_jobs=job_count)

        self.message_user(
            request,
            f"Queued {job_count} translation jobs for background processing. Check back in a few minutes.",
        )

    process_all_pending_jobs.short_description = "Queue all pending jobs (max 50)"


@admin.register(AnalysisJob)
class AnalysisJobAdmin(admin.ModelAdmin):
    list_display = [
        "chapter",
        "status",
        "characters_found",
        "places_found",
        "terms_found",
        "retry_count",
        "created_at",
    ]
    list_filter = ["status", "created_at"]
    search_fields = ["chapter__title", "chapter__book__title"]
    readonly_fields = [
        "pk",
        "created_at",
        "updated_at",
        "characters_found",
        "places_found",
        "terms_found",
        "retry_count",
        "celery_task_id",
    ]
    ordering = ["-created_at"]
    actions = ["retry_failed_jobs"]

    def retry_failed_jobs(self, request, queryset):
        """Retry selected failed analysis jobs"""
        from books.choices import ProcessingStatus
        from books.tasks import analyze_chapter_entities

        failed_jobs = queryset.filter(status=ProcessingStatus.FAILED)
        job_count = failed_jobs.count()

        if job_count == 0:
            self.message_user(request, "No failed jobs selected")
            return

        # Reset status and trigger tasks
        for job in failed_jobs:
            job.status = ProcessingStatus.PENDING
            job.error_message = ""
            job.save()
            analyze_chapter_entities.delay(job.chapter.id)

        self.message_user(
            request,
            f"Retrying {job_count} analysis jobs. Check back in a few minutes.",
        )

    retry_failed_jobs.short_description = "Retry failed analysis jobs"


@admin.register(FileUploadJob)
class FileUploadJobAdmin(admin.ModelAdmin):
    list_display = [
        "book",
        "status",
        "created_by",
        "auto_create_chapters",
        "detected_chapter_count",
        "created_chapter_count",
        "created_at",
    ]
    list_filter = ["status", "auto_create_chapters", "created_at"]
    search_fields = ["book__title", "created_by__username"]
    readonly_fields = [
        "pk",
        "created_at",
        "updated_at",
        "word_count",
        "character_count",
        "detected_chapter_count",
        "created_chapter_count",
        "celery_task_id",
    ]
    ordering = ["-created_at"]

    fieldsets = (
        (
            None,
            {"fields": ("book", "created_by", "status", "auto_create_chapters")},
        ),
        (
            "Job Results",
            {
                "fields": (
                    "word_count",
                    "character_count",
                    "detected_chapter_count",
                    "created_chapter_count",
                    "error_message",
                ),
            },
        ),
        (
            "Technical",
            {
                "fields": ("celery_task_id", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )


# ============================================================================
# CONTEXT/ENTITY ADMINS
# ============================================================================


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
    readonly_fields = ["pk", "created_at", "updated_at"]
    ordering = ["bookmaster", "entity_type", "source_name"]

    fieldsets = (
        (
            None,
            {"fields": ("pk", "bookmaster", "entity_type", "source_name", "first_chapter")},
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
    readonly_fields = ["pk", "created_at", "updated_at", "entity_count"]
    ordering = ["-updated_at"]
    actions = ["extract_entities_for_selected", "clear_analysis"]

    fieldsets = (
        (None, {"fields": ("pk", "chapter")}),
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


# ============================================================================
# STATISTICS ADMINS
# ============================================================================


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
