from .bookmaster import (
    BookMasterCreateView,
    BookMasterListView,
    BookMasterDetailView,
    BookMasterUpdateView,
    BookMasterDeleteView,
)
from .chaptermaster import (
    ChapterMasterCreateView,
    ChapterMasterDetailView,
    ChapterMasterUpdateView,
    ChapterMasterDeleteView,
)
from .book import (
    BookCreateView,
    BookDetailView,
    BookUpdateView,
    BookDeleteView,
    BookFileUploadView,
)
from .chapter import (
    ChapterCreateView,
    ChapterDetailView,
    ChapterUpdateView,
    ChapterDeleteView,
)
from .entity import (
    BookEntityListView,
    BookEntityUpdateView,
    BookEntityDeleteView,
)
from .task import (
    TaskListView,
    TaskCountView,
    TaskActionView,
)
from .translation import (
    ChapterTranslationView,
    BatchActionView,
)
from .stats import (
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
    # Chapter
    "ChapterCreateView",
    "ChapterDetailView",
    "ChapterUpdateView",
    "ChapterDeleteView",
    # Entity
    "BookEntityListView",
    "BookEntityUpdateView",
    "BookEntityDeleteView",
    # Task
    "TaskListView",
    "TaskCountView",
    "TaskActionView",
    # Translation
    "ChapterTranslationView",
    "BatchActionView",
    # Stats
    "update_reading_progress",
]
