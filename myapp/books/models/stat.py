"""
Analytics and statistics models.

This module contains models for tracking views and engagement:
- ViewEvent: Time-series event log for detailed analytics
- ChapterStats: Aggregated statistics for chapters
- BookStats: Aggregated statistics for books
"""

from django.db import models

from common.models import TimeStampedModel


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


class ChapterStats(TimeStampedModel):
    """Statistics for individual chapters (session-based anonymous tracking)"""

    chapter = models.OneToOneField(
        "Chapter",
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
        "Book",
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
                from books.stats import StatsService
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
