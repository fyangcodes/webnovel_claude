from .bookmaster_views import (
    BookMasterCreateView,
    BookMasterListView,
    BookMasterDetailView,
    BookMasterUpdateView,
    BookMasterDeleteView,
)
from .chaptermaster_views import (
    ChapterMasterCreateView,
    ChapterMasterDetailView,
    ChapterMasterUpdateView,
    ChapterMasterDeleteView,
)
from .book_views import (
    BookCreateView,
    BookDetailView,
    BookUpdateView,
    BookDeleteView,
    BookFileUploadView,
    UploadJobStatusView,
)
from .chapter_views import (
    ChapterCreateView,
    ChapterDetailView,
    ChapterUpdateView,
    ChapterDeleteView,
)
from .utils_views import (
    ChapterTranslationView,
    TaskStatusView,
    BatchActionView,
)
from .entity_views import (
    BookEntityListView,
    BookEntityUpdateView,
    BookEntityDeleteView,
)
from .stats_views import (
    update_reading_progress,
)

__all__ = [
    # Bookmaster
    "BookMasterCreateView",
    "BookMasterListView",
    "BookMasterDetailView",
    "BookMasterUpdateView",
    "BookMasterDeleteView",
    # Chaptermaster
    "ChapterMasterCreateView",
    "ChapterMasterDetailView",
    "ChapterMasterUpdateView",
    "ChapterMasterDeleteView",
    # Book
    "BookCreateView",
    "BookDetailView",
    "BookUpdateView",
    "BookDeleteView",
    "BookFileUploadView",
    "UploadJobStatusView",
    # Chapter
    "ChapterCreateView",
    "ChapterDetailView",
    "ChapterUpdateView",
    "ChapterDeleteView",
    # Entity
    "BookEntityListView",
    "BookEntityUpdateView",
    "BookEntityDeleteView",
    # Utils
    "ChapterTranslationView",
    "TaskStatusView",
    "BatchActionView",
    # Stats
    "update_reading_progress",
]
