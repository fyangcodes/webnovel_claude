"""
Reader app views package.

This package organizes views into logical modules:

- base: Base view classes (BaseReaderView, BaseBookListView, BaseBookDetailView)
- list_views: List views (WelcomeView, BookListView, BookSearchView)
- detail_views: Detail views (BookDetailView, ChapterDetailView)
- redirect_views: Redirect views (GenreBookListView, TagBookListView)
- section_views: Section-scoped views (NEW in Phase 1)
- legacy_views: Legacy redirect views for backward compatibility (NEW in Phase 1)

All views are exported for backward compatibility with existing URLs.
"""

# Base classes (for subclassing)
from .base import BaseReaderView, BaseBookListView, BaseBookDetailView

# List views
from .list_views import WelcomeView, BookListView, BookSearchView

# Detail views
from .detail_views import BookDetailView, ChapterDetailView

# Redirect views
from .redirect_views import GenreBookListView, TagBookListView

# Section-scoped views (Phase 1)
from .section_views import (
    SectionHomeView,
    SectionBookListView,
    SectionBookDetailView,
    SectionChapterDetailView,
    SectionSearchView,
    SectionGenreBookListView,
    SectionTagBookListView,
)

# Legacy redirect views (Phase 1)
from .legacy_views import (
    LegacyBookDetailRedirectView,
    LegacyChapterDetailRedirectView,
)

# SEO views (Phase 5)
from .robots import RobotsTxtView

# Export all views for backward compatibility
__all__ = [
    # Base classes
    "BaseReaderView",
    "BaseBookListView",
    "BaseBookDetailView",
    # List views
    "WelcomeView",
    "BookListView",
    "BookSearchView",
    # Detail views
    "BookDetailView",
    "ChapterDetailView",
    # Redirect views
    "GenreBookListView",
    "TagBookListView",
    # Section-scoped views
    "SectionHomeView",
    "SectionBookListView",
    "SectionBookDetailView",
    "SectionChapterDetailView",
    "SectionSearchView",
    "SectionGenreBookListView",
    "SectionTagBookListView",
    # Legacy redirect views
    "LegacyBookDetailRedirectView",
    "LegacyChapterDetailRedirectView",
    # SEO views
    "RobotsTxtView",
]
