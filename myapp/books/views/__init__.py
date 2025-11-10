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
    "BatchActionView"
]
