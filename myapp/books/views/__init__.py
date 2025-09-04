from .bookmaster_views import (
    BookMasterCreateView,
    BookMasterListView,
    BookMasterDetailView,
    BookMasterUpdateView,
    BookMasterDeleteView,
    BatchChapterActionView,
)
from .book_views import (
    BookCreateView,
    BookDetailView,
    BookUpdateView,
    BookDeleteView,
    BookFileUploadView,
    BatchChapterActionView as BookBatchChapterActionView,
)
from .chapter_views import (
    ChapterCreateView,
    ChapterDetailView,
    ChapterUpdateView,
    ChapterDeleteView,
)
from .chaptermaster_views import (
    ChapterMasterCreateView,
    ChapterMasterDetailView,
    ChapterMasterUpdateView,
    ChapterMasterDeleteView,
)
from .utils_views import (
    ChapterTranslationView,
    TaskStatusView,
)

__all__ = [
    "BookMasterCreateView",
    "BookMasterListView",
    "BookMasterDetailView",
    "BookMasterUpdateView",
    "BookMasterDeleteView",
    "BatchChapterActionView",
    "BookCreateView",
    "BookDetailView",
    "BookUpdateView",
    "BookDeleteView",
    "BookFileUploadView",
    "BookBatchChapterActionView",
    "ChapterCreateView",
    "ChapterDetailView",
    "ChapterUpdateView",
    "ChapterDeleteView",
    "ChapterTranslationView",
    "ChapterMasterCreateView",
    "ChapterMasterDetailView",
    "ChapterMasterUpdateView",
    "ChapterMasterDeleteView",
    "TaskStatusView",
]
