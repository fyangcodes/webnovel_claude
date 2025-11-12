"""
Books tasks package for Celery async processing.

This package organizes Celery tasks by concern:
- analytics: Stats aggregation, trending scores, view event cleanup
- chapter_analysis: AI entity extraction and chapter summarization
- chapter_translation: Translation job processing
- text_extraction: File upload processing and chapter creation

All tasks are exported at the package level for Celery autodiscovery.
"""

# Analytics tasks
from .analytics import (
    aggregate_stats_hourly,
    update_time_period_uniques,
    cleanup_old_view_events,
    calculate_trending_scores,
)

# Chapter analysis tasks
from .chapter_analysis import (
    analyze_chapter_entities,
)

# Chapter translation tasks
from .chapter_translation import (
    process_translation_jobs,
)

# Text extraction tasks
from .text_extraction import (
    process_file_upload,
)

__all__ = [
    # Analytics
    "aggregate_stats_hourly",
    "update_time_period_uniques",
    "cleanup_old_view_events",
    "calculate_trending_scores",
    # Chapter analysis
    "analyze_chapter_entities",
    # Chapter translation
    "process_translation_jobs",
    # Text extraction
    "process_file_upload",
]
