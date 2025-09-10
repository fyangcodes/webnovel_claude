from django.contrib import admin
from .models import Language, BookMaster, Book, ChapterMaster, Chapter, TranslationJob


@admin.register(Language)
class LanguageAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "local_name"]
    search_fields = ["name", "code", "local_name"]
    ordering = ["name"]


@admin.register(BookMaster)
class BookMasterAdmin(admin.ModelAdmin):
    list_display = ["canonical_title", "owner", "original_language", "created_at"]
    list_filter = ["original_language", "created_at"]
    search_fields = ["canonical_title"]
    ordering = ["canonical_title"]


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


@admin.register(TranslationJob)
class TranslationJobAdmin(admin.ModelAdmin):
    list_display = ["chapter", "target_language", "status", "created_by", "created_at", "updated_at"]
    list_filter = ["status", "target_language", "created_at"]
    search_fields = ["chapter__title", "target_language__name", "created_by__username"]
    readonly_fields = ["created_at", "updated_at"]
    ordering = ["-created_at"]
    actions = ["process_selected_jobs", "process_all_pending_jobs"]

    def process_selected_jobs(self, request, queryset):
        """Process selected translation jobs"""
        from translation.services import TranslationService
        from books.choices import ProcessingStatus
        
        service = TranslationService()
        success_count = 0
        error_count = 0
        
        for job in queryset.filter(status=ProcessingStatus.PENDING):
            try:
                job.status = ProcessingStatus.PROCESSING
                job.save()
                
                service.translate_chapter(job.chapter, job.target_language.code)
                
                job.status = ProcessingStatus.COMPLETED
                job.error_message = ""
                job.save()
                success_count += 1
                
            except Exception as e:
                job.status = ProcessingStatus.FAILED
                job.error_message = str(e)
                job.save()
                error_count += 1
        
        if success_count:
            self.message_user(request, f"Successfully processed {success_count} translation jobs")
        if error_count:
            self.message_user(request, f"Failed to process {error_count} translation jobs", level="ERROR")
    
    process_selected_jobs.short_description = "Process selected translation jobs"

    def process_all_pending_jobs(self, request, queryset=None):
        """Process all pending translation jobs (up to 50 at once)"""
        from translation.services import process_translation_jobs
        
        try:
            process_translation_jobs(max_jobs=50)
            self.message_user(request, "Translation job processing completed")
        except Exception as e:
            self.message_user(request, f"Error processing translation jobs: {e}", level="ERROR")
    
    process_all_pending_jobs.short_description = "Process all pending jobs (max 50)"
