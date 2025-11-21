"""
Books models package.

This package organizes models by concern:
- base: TimeStampModel, LocalizationModel, SlugGeneratorMixin
- core: Language, BookMaster, Book, ChapterMaster, Chapter
- taxonomy: Section, Genre, BookGenre, Tag, BookTag, BookKeyword, Author
- job: TranslationJob, AnalysisJob, FileUploadJob
- context: BookEntity, ChapterContext
- stat: ViewEvent, ChapterStats, BookStats
"""

from .base import TimeStampModel, LocalizationModel, SlugGeneratorMixin
from .core import (
    Language,
    BookMaster,
    Book,
    ChapterMaster,
    Chapter,
)
from .taxonomy import (
    Section,
    Genre,
    BookGenre,
    Tag,
    BookTag,
    BookKeyword,
    Author,
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
    # Base
    "TimeStampModel",
    "LocalizationModel",
    "SlugGeneratorMixin",
    # Core - Content models
    "Language",
    "BookMaster",
    "Book",
    "ChapterMaster",
    "Chapter",
    # Taxonomy - Classification models
    "Section",
    "Genre",
    "BookGenre",
    "Tag",
    "BookTag",
    "BookKeyword",
    "Author",
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
