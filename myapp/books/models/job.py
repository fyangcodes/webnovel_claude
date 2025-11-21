"""
Background job tracking models.

This module contains models for tracking async background jobs:
- TranslationJob: Track chapter translation tasks
- AnalysisJob: Track AI entity extraction and analysis tasks
- FileUploadJob: Track file upload and chapter creation tasks
"""

from django.conf import settings
from django.db import models

from books.models.base import TimeStampModel
from books.choices import ProcessingStatus


class TranslationJob(TimeStampModel):
    """Track async chapter translation jobs"""

    chapter = models.ForeignKey(
        "Chapter",
        on_delete=models.CASCADE,
        related_name="translation_jobs",
    )
    target_language = models.ForeignKey(
        "Language",
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

    # Celery task ID for tracking
    celery_task_id = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Translation Job"
        verbose_name_plural = "Jobs - Translation Jobs"
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["chapter", "status"]),
        ]

    def __str__(self):
        return f"Translation of {self.chapter.title} (#{self.chapter.pk}) to {self.target_language.name}"


class AnalysisJob(TimeStampModel):
    """Track async AI entity extraction and chapter analysis jobs"""

    chapter = models.ForeignKey(
        "Chapter",
        on_delete=models.CASCADE,
        related_name="analysis_jobs",
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
        help_text="User who created the chapter or initiated the analysis",
    )
    error_message = models.TextField(blank=True)
    retry_count = models.PositiveIntegerField(default=0)

    # Analysis results summary
    characters_found = models.PositiveIntegerField(default=0)
    places_found = models.PositiveIntegerField(default=0)
    terms_found = models.PositiveIntegerField(default=0)

    # Celery task ID for tracking
    celery_task_id = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Analysis Job"
        verbose_name_plural = "Jobs - Analysis Jobs"
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["chapter", "status"]),
        ]

    def __str__(self):
        return f"Analysis of {self.chapter.title} (#{self.chapter.pk})"


class FileUploadJob(TimeStampModel):
    """Track async file upload and chapter creation jobs"""

    book = models.ForeignKey(
        "Book",
        on_delete=models.CASCADE,
        related_name="upload_jobs",
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
    auto_create_chapters = models.BooleanField(default=True)

    # Job results
    error_message = models.TextField(blank=True)
    word_count = models.PositiveIntegerField(default=0)
    character_count = models.PositiveIntegerField(default=0)
    detected_chapter_count = models.PositiveIntegerField(default=0)
    created_chapter_count = models.PositiveIntegerField(default=0)

    # Celery task ID for tracking
    celery_task_id = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "File Upload Job"
        verbose_name_plural = "Jobs - File Upload Jobs"
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["book", "status"]),
        ]

    def __str__(self):
        return f"Upload job for {self.book.title} - {self.status}"
