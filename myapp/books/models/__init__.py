"""
Books models package.

This package organizes models by concern:
- core: Language, BookMaster, Book, ChapterMaster, Chapter
- taxonomy: Section, Genre, BookGenre, Tag, BookTag, BookKeyword
- job: TranslationJob, AnalysisJob, FileUploadJob
- context: BookEntity, ChapterContext
- stat: ViewEvent, ChapterStats, BookStats
"""

from .core import (
    SlugGeneratorMixin,
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
