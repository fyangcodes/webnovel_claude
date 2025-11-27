"""
Reader app views package.

This package organizes views into logical modules:

- base: Base view classes (BaseReaderView, BaseBookListView, BaseBookDetailView)
- list_views: List views (WelcomeView, BookSearchView)
- detail_views: Author detail view (AuthorDetailView)
- section_views: Section-scoped views (book/chapter detail, genre/tag redirects)
- robots: SEO views (RobotsTxtView)

All views are exported for backward compatibility with existing URLs.
"""

# Base classes (for subclassing)
from .base import (
    BaseReaderView,
    BaseBookListView,
    BaseBookDetailView,
)

# List views
from .general import (
    WelcomeView,
    BookSearchView,
    AuthorDetailView,
)

# Section-scoped views
from .section import (
    SectionHomeView,
    SectionBookListView,
    SectionBookDetailView,
    SectionChapterDetailView,
    SectionGenreBookListView,
    SectionTagBookListView,
)

# SEO views
from .robots import RobotsTxtView

# Export all views
__all__ = [
    # Base classes
    "BaseReaderView",
    "BaseBookListView",
    "BaseBookDetailView",
    # List views
    "WelcomeView",
    "BookSearchView",
    "AuthorDetailView",
    # Section-scoped views
    "SectionHomeView",
    "SectionBookListView",
    "SectionBookDetailView",
    "SectionChapterDetailView",
    "SectionGenreBookListView",
    "SectionTagBookListView",
    # SEO views
    "RobotsTxtView",
]
