"""
Books models package.

This package organizes models by concern:
- core: Language, Genre, BookMaster, Book, ChapterMaster, Chapter
- job: TranslationJob, AnalysisJob, FileUploadJob
- context: BookEntity, ChapterContext
- stat: ViewEvent, ChapterStats, BookStats
"""

from .core import (
    SlugGeneratorMixin,
    Language,
    Genre,
    BookGenre,
    BookMaster,
    Book,
    ChapterMaster,
    Chapter,
)
from .job import (
    TranslationJob,
    AnalysisJob,
    FileUploadJob,
)
from .context import (
    BookEntity,
    ChapterContext,
)
from .stat import (
    ViewEvent,
    ChapterStats,
    BookStats,
)

__all__ = [
    # Core - Mixins
    "SlugGeneratorMixin",
    # Core - Content models
    "Language",
    "Genre",
    "BookGenre",
    "BookMaster",
    "Book",
    "ChapterMaster",
    "Chapter",
    # Jobs
    "TranslationJob",
    "AnalysisJob",
    "FileUploadJob",
    # Context
    "BookEntity",
    "ChapterContext",
    # Stats
    "ViewEvent",
    "ChapterStats",
    "BookStats",
]
