"""
Signal handlers package for the books app.

This package organizes signal handlers by concern:
- cache: Cache invalidation signals for fresh data
- keywords: BookKeyword auto-population for search infrastructure
- entities: BookEntity auto-rebuild for occurrence tracking

All signal modules are imported here to ensure they're registered when
the app starts (via apps.py ready() method).
"""

# Import all signal modules to register them
from . import cache  # noqa: F401
from . import keywords  # noqa: F401
from . import entities  # noqa: F401
