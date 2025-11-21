# Reader App Caching Analysis

## Current Caching Status

The reader app has a well-organized caching system in `reader/cache/` with the following modules:

| Module | Purpose | TTL |
|--------|---------|-----|
| `static_data.py` | Languages, Sections, Genres, Tags | 1 hour |
| `metadata.py` | Chapter counts, stats | 30 min |
| `homepage.py` | Featured books, carousels | 10 min |
| `chapters.py` | Chapter lists, navigation | 30 min |

## Views Caching Coverage

**Well-cached views:**
- `BaseReaderView.get_context_data()` - Uses `get_cached_languages`, `get_cached_sections`, `get_cached_genres`, `get_cached_genres_flat`, `get_cached_tags`
- `BaseBookListView.enrich_books_with_metadata()` - Uses `get_cached_chapter_count`, `get_cached_total_chapter_views`
- `WelcomeView` - Uses `get_cached_featured_genres`, `get_cached_featured_books`, `get_cached_recently_updated`, `get_cached_new_arrivals`
- `SectionChapterDetailView` - Uses `get_cached_chapter_navigation`
- `SectionBookDetailView` - Uses `get_cached_total_chapter_views`

---

## StyleConfig Model - NO CACHING

The `StyleConfig` model in `reader/models.py` is **NOT cached** at all.

| Issue | Impact |
|-------|--------|
| No caching functions exist | Every view that needs styling will query DB |
| No signal handlers for invalidation | N/A (no cache to invalidate) |
| Generic ForeignKey lookup | Can be expensive if used frequently |

### Recommendations for StyleConfig Caching

1. **Add cache functions** in `reader/cache/static_data.py`:
   - `get_cached_style_config(content_type_id, object_id)` - Get style for a specific object
   - `get_cached_styles_by_type(content_type_id)` - Get all styles for a model type (e.g., all Section styles)

2. **Add signal handlers** in `books/signals/cache.py`:
   - Invalidate style cache when `StyleConfig` is saved/deleted

3. **Suggested cache key pattern**:
   - `styleconfig:{content_type_id}:{object_id}` - Individual style
   - `styleconfig:type:{content_type_id}` - All styles for a model type

4. **TTL**: 1 hour (same as other static/admin-managed data)

---

## N+1 Query Issues Breakdown

### 1. `enrich_books_with_metadata()` - Cache calls per book

**Location**: `reader/views/base.py:243-265`

```python
for book in books:
    book.published_chapters_count = cache.get_cached_chapter_count(book.id)  # 1 cache call per book
    book.total_chapter_views = cache.get_cached_total_chapter_views(book.id)  # 1 cache call per book
```

**Impact**: For a list of 12 books, this makes **24 cache lookups** (12 x 2). While cache is fast, this could be optimized with bulk fetching via `cache.get_many()`.

**Recommendation**: Create bulk cache functions:
- `get_cached_chapter_counts_bulk(book_ids)` - Returns dict `{book_id: count}`
- `get_cached_total_chapter_views_bulk(book_ids)` - Returns dict `{book_id: views}`

---

### 2. `enrich_books_with_metadata()` - Genre parent access

**Location**: `reader/views/base.py:259-260`

```python
for genre in book.bookmaster.genres.all():
    if genre.parent:
        genre.parent_localized_name = genre.parent.get_localized_name(language_code)
```

**Status**: RESOLVED - The querysets in list views use:
```python
.prefetch_related("bookmaster__genres", "bookmaster__genres__parent", "bookmaster__genres__section")
```

---

### 3. `BookDetailView.get_context_data()` - Chapter iteration

**Location**: `reader/views/detail_views.py:68-71`

```python
all_chapters = self.object.chapters.filter(is_public=True)...
context["total_chapters"] = all_chapters.count()  # Query 1
context["total_words"] = sum(chapter.effective_count for chapter in all_chapters)  # Query 2 (iterates all)
latest_chapter = all_chapters.order_by("-published_at").first()  # Query 3
```

**Issue**: `all_chapters` queryset is evaluated **3 separate times**:
- `.count()` - 1 query
- `sum(...)` iteration - 1 query (fetches all rows)
- `.order_by().first()` - 1 query

**Recommendation**: Evaluate queryset once:
```python
all_chapters_list = list(all_chapters)
context["total_chapters"] = len(all_chapters_list)
context["total_words"] = sum(chapter.effective_count for chapter in all_chapters_list)
latest_chapter = max(all_chapters_list, key=lambda c: c.published_at, default=None)
```

Or use Django aggregation:
```python
from django.db.models import Sum, Max, Count
stats = all_chapters.aggregate(
    total=Count('id'),
    total_words=Sum('word_count'),
    last_update=Max('published_at')
)
```

---

### 4. `ChapterDetailView.get_context_data()` - Previous/Next chapter fetch

**Location**: `reader/views/detail_views.py:131-143`

```python
if nav_data['previous']:
    context["previous_chapter"] = Chapter.objects.filter(id=nav_data['previous']['id']).first()  # Query
if nav_data['next']:
    context["next_chapter"] = Chapter.objects.filter(id=nav_data['next']['id']).first()  # Query
```

**Issue**: After getting cached navigation data, it makes **2 additional queries** to fetch the actual Chapter objects.

**Recommendation**: Fetch both in one query:
```python
chapter_ids = [nav_data['previous']['id'], nav_data['next']['id']]
chapter_ids = [cid for cid in chapter_ids if cid]  # Filter None
chapters_map = {c.id: c for c in Chapter.objects.filter(id__in=chapter_ids)}
context["previous_chapter"] = chapters_map.get(nav_data['previous']['id']) if nav_data['previous'] else None
context["next_chapter"] = chapters_map.get(nav_data['next']['id']) if nav_data['next'] else None
```

---

### 5. `SectionBookDetailView` / `SectionChapterDetailView`

**Location**: `reader/views/section_views.py`

These inherit the same patterns from `BookDetailView` and `ChapterDetailView`, so they have the same issues as #3 and #4.

---

## Summary Table

| Location | Issue | Queries/Calls | Severity | Status |
|----------|-------|---------------|----------|--------|
| `enrich_books_with_metadata` | Cache calls in loop | 24 cache hits/page | Low | TODO |
| `BookDetailView.get_context_data` | Triple queryset evaluation | 3 queries | Medium | TODO |
| `ChapterDetailView.get_context_data` | Separate prev/next queries | 2 queries | Low | TODO |
| Genre/Section localization | Parent/section access | 0 (prefetched) | N/A | RESOLVED |
| `StyleConfig` | No caching at all | 1+ queries per use | Medium | TODO |

---

## Implementation Priority

1. **High**: StyleConfig caching (new feature, needs foundation)
2. **Medium**: BookDetailView triple evaluation (affects every book page)
3. **Low**: Cache bulk operations (optimization, cache is already fast)
4. **Low**: ChapterDetailView prev/next (only 2 small queries)

---

## Detailed Implementation Steps

### Task 1: StyleConfig Caching

#### Step 1.1: Add cache functions to `reader/cache/static_data.py`

Add the following functions at the end of the file:

```python
# ==============================================================================
# STYLECONFIG CACHING
# ==============================================================================


def get_cached_style_config(content_type_id, object_id):
    """
    Get StyleConfig for a specific object from cache or database.

    Cache key: styleconfig:{content_type_id}:{object_id}
    TTL: 1 hour (rarely changes, admin-only)
    Invalidated by: StyleConfig model save/delete signals

    Args:
        content_type_id: ContentType ID for the model
        object_id: Primary key of the object

    Returns:
        StyleConfig object or None if not found
    """
    from reader.models import StyleConfig

    cache_key = f"styleconfig:{content_type_id}:{object_id}"
    style = cache.get(cache_key)

    if style is None:
        try:
            style = StyleConfig.objects.get(
                content_type_id=content_type_id,
                object_id=object_id
            )
        except StyleConfig.DoesNotExist:
            style = False  # Use False to distinguish "not found" from "not cached"

        cache.set(cache_key, style, timeout=TIMEOUT_STATIC)

    return style if style is not False else None


def get_cached_styles_for_model(model_class):
    """
    Get all StyleConfigs for a model type from cache or database.

    Useful for bulk lookups (e.g., get all Section styles at once).

    Cache key: styleconfig:model:{app_label}.{model_name}
    TTL: 1 hour
    Invalidated by: StyleConfig model save/delete signals

    Args:
        model_class: Django model class (e.g., Section, Genre)

    Returns:
        dict: {object_id: StyleConfig} for all objects of this model type
    """
    from django.contrib.contenttypes.models import ContentType
    from reader.models import StyleConfig

    content_type = ContentType.objects.get_for_model(model_class)
    cache_key = f"styleconfig:model:{content_type.app_label}.{content_type.model}"

    styles_dict = cache.get(cache_key)

    if styles_dict is None:
        styles = StyleConfig.objects.filter(content_type=content_type)
        styles_dict = {style.object_id: style for style in styles}
        cache.set(cache_key, styles_dict, timeout=TIMEOUT_STATIC)

    return styles_dict


def invalidate_style_config_cache(content_type_id, object_id):
    """
    Invalidate StyleConfig cache for a specific object.

    Called by signal handlers when StyleConfig is saved/deleted.
    """
    from django.contrib.contenttypes.models import ContentType

    # Invalidate individual style cache
    cache.delete(f"styleconfig:{content_type_id}:{object_id}")

    # Invalidate model-level cache
    try:
        content_type = ContentType.objects.get(id=content_type_id)
        cache.delete(f"styleconfig:model:{content_type.app_label}.{content_type.model}")
    except ContentType.DoesNotExist:
        pass
```

#### Step 1.2: Export new functions in `reader/cache/__init__.py`

Add to imports:
```python
from .static_data import (
    # ... existing imports ...
    get_cached_style_config,
    get_cached_styles_for_model,
    invalidate_style_config_cache,
)
```

Add to `__all__`:
```python
__all__ = [
    # ... existing exports ...
    # StyleConfig
    "get_cached_style_config",
    "get_cached_styles_for_model",
    "invalidate_style_config_cache",
]
```

#### Step 1.3: Add signal handlers in `books/signals/cache.py`

Add at the end of the file:

```python
# ==============================================================================
# STYLECONFIG SIGNALS
# ==============================================================================

from reader.models import StyleConfig

@receiver([post_save, post_delete], sender=StyleConfig)
def invalidate_styleconfig_caches(sender, instance, **kwargs):
    """
    Invalidate StyleConfig caches when a style is created, updated, or deleted.

    Affected caches:
    1. Individual style cache for this object
    2. Model-level cache for this content type
    """
    from reader.cache import invalidate_style_config_cache

    invalidate_style_config_cache(instance.content_type_id, instance.object_id)
```

#### Step 1.4: Usage example in views

```python
from reader import cache
from django.contrib.contenttypes.models import ContentType
from books.models import Section

# Option 1: Get individual style
content_type = ContentType.objects.get_for_model(Section)
style = cache.get_cached_style_config(content_type.id, section.id)

# Option 2: Get all section styles at once (more efficient for lists)
section_styles = cache.get_cached_styles_for_model(Section)
style = section_styles.get(section.id)  # Returns StyleConfig or None
```

---

### Task 2: Fix BookDetailView Triple Queryset Evaluation

#### Step 2.1: Update `reader/views/detail_views.py` - `BookDetailView.get_context_data()`

Replace lines 51-75:

```python
def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)

    # Get all published chapters - evaluate ONCE as a list
    all_chapters = list(
        self.object.chapters.filter(is_public=True)
        .select_related("chaptermaster")
        .order_by("chaptermaster__chapter_number")
    )

    # Pagination for chapters
    paginator = Paginator(all_chapters, 20)  # 20 chapters per page
    page_number = self.request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context["chapters"] = page_obj
    context["is_paginated"] = page_obj.has_other_pages()
    context["page_obj"] = page_obj

    # Reading progress context - use already-fetched list (NO additional queries)
    context["total_chapters"] = len(all_chapters)
    context["total_words"] = sum(
        chapter.effective_count for chapter in all_chapters
    )

    # Last update from most recently published chapter (in-memory sort)
    if all_chapters:
        latest_chapter = max(
            all_chapters,
            key=lambda c: c.published_at or c.created_at
        )
        context["last_update"] = latest_chapter.published_at
    else:
        context["last_update"] = None

    # Add total chapter views from cache
    context["total_chapter_views"] = cache.get_cached_total_chapter_views(self.object.id)

    # Create ViewEvent immediately for tracking (before template renders)
    from books.stats import StatsService
    view_event = StatsService.track_book_view(self.object, self.request)
    context["view_event_id"] = view_event.id if view_event else None

    return context
```

#### Step 2.2: Apply same fix to `reader/views/section_views.py` - `SectionBookDetailView.get_context_data()`

Replace lines 284-307 with the same pattern:

```python
def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    section = self.get_section()

    # Show section nav on book detail (for discoverability)
    context['show_section_nav'] = True

    # Get all published chapters - evaluate ONCE as a list
    all_chapters = list(
        self.object.chapters.filter(is_public=True)
        .select_related("chaptermaster")
        .order_by("chaptermaster__chapter_number")
    )

    # Pagination for chapters
    paginator = Paginator(all_chapters, 20)  # 20 chapters per page
    page_number = self.request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context["chapters"] = page_obj
    context["is_paginated"] = page_obj.has_other_pages()
    context["page_obj"] = page_obj

    # Reading progress context - use already-fetched list (NO additional queries)
    context["total_chapters"] = len(all_chapters)
    context["total_words"] = sum(
        chapter.effective_count for chapter in all_chapters
    )

    # Last update from most recently published chapter (in-memory sort)
    if all_chapters:
        latest_chapter = max(
            all_chapters,
            key=lambda c: c.published_at or c.created_at
        )
        context["last_update"] = latest_chapter.published_at
    else:
        context["last_update"] = None

    # Add total chapter views from cache
    context["total_chapter_views"] = cache.get_cached_total_chapter_views(self.object.id)

    # Create ViewEvent immediately for tracking (before template renders)
    from books.stats import StatsService
    view_event = StatsService.track_book_view(self.object, self.request)
    context["view_event_id"] = view_event.id if view_event else None

    return context
```

---

### Task 3: Fix ChapterDetailView Separate Prev/Next Queries

#### Step 3.1: Update `reader/views/detail_views.py` - `ChapterDetailView.get_context_data()`

Replace lines 130-143:

```python
def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    context["book"] = self.object.book

    # Get cached navigation data (eliminates 4 queries: previous, next, position, total)
    current_chapter_number = self.object.chaptermaster.chapter_number
    nav_data = cache.get_cached_chapter_navigation(
        self.object.book.id,
        current_chapter_number
    )

    # Fetch previous and next chapters in ONE query
    chapter_ids = []
    if nav_data['previous']:
        chapter_ids.append(nav_data['previous']['id'])
    if nav_data['next']:
        chapter_ids.append(nav_data['next']['id'])

    if chapter_ids:
        chapters_map = {c.id: c for c in Chapter.objects.filter(id__in=chapter_ids)}
    else:
        chapters_map = {}

    context["previous_chapter"] = chapters_map.get(nav_data['previous']['id']) if nav_data['previous'] else None
    context["next_chapter"] = chapters_map.get(nav_data['next']['id']) if nav_data['next'] else None
    context["chapter_position"] = nav_data['position']
    context["total_chapters"] = nav_data['total']

    # Create ViewEvent immediately for tracking (before template renders)
    from books.stats import StatsService
    view_event = StatsService.track_chapter_view(self.object, self.request)
    context["view_event_id"] = view_event.id if view_event else None

    return context
```

#### Step 3.2: Apply same fix to `reader/views/section_views.py` - `SectionChapterDetailView.get_context_data()`

Replace lines 372-400:

```python
def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    book = self.object.book
    context["book"] = book

    # HIDE section nav on chapter reading (reading immersion priority)
    context['show_section_nav'] = False

    # Add section localized name to book for template
    language_code = self.kwargs.get("language_code")
    if book.bookmaster and book.bookmaster.section:
        book.section_localized_name = book.bookmaster.section.get_localized_name(language_code)

    # Get cached navigation data (eliminates 4 queries: previous, next, position, total)
    current_chapter_number = self.object.chaptermaster.chapter_number
    nav_data = cache.get_cached_chapter_navigation(
        self.object.book.id,
        current_chapter_number
    )

    # Fetch previous and next chapters in ONE query
    chapter_ids = []
    if nav_data['previous']:
        chapter_ids.append(nav_data['previous']['id'])
    if nav_data['next']:
        chapter_ids.append(nav_data['next']['id'])

    if chapter_ids:
        chapters_map = {c.id: c for c in Chapter.objects.filter(id__in=chapter_ids)}
    else:
        chapters_map = {}

    context["previous_chapter"] = chapters_map.get(nav_data['previous']['id']) if nav_data['previous'] else None
    context["next_chapter"] = chapters_map.get(nav_data['next']['id']) if nav_data['next'] else None
    context["chapter_position"] = nav_data['position']
    context["total_chapters"] = nav_data['total']

    # Create ViewEvent immediately for tracking (before template renders)
    from books.stats import StatsService
    view_event = StatsService.track_chapter_view(self.object, self.request)
    context["view_event_id"] = view_event.id if view_event else None

    return context
```

---

### Task 4: Add Bulk Cache Functions (Optional Optimization)

#### Step 4.1: Add bulk functions to `reader/cache/metadata.py`

```python
def get_cached_chapter_counts_bulk(book_ids):
    """
    Get chapter counts for multiple books in one cache operation.

    Uses cache.get_many() for efficiency.

    Args:
        book_ids: List of book IDs

    Returns:
        dict: {book_id: chapter_count}
    """
    if not book_ids:
        return {}

    # Build cache keys
    cache_keys = [f"book:{book_id}:chapter_count" for book_id in book_ids]
    key_to_book_id = {f"book:{book_id}:chapter_count": book_id for book_id in book_ids}

    # Get from cache
    cached = cache.get_many(cache_keys)

    # Find missing keys
    result = {}
    missing_book_ids = []

    for cache_key, book_id in key_to_book_id.items():
        if cache_key in cached:
            result[book_id] = cached[cache_key]
        else:
            missing_book_ids.append(book_id)

    # Fetch missing from database
    if missing_book_ids:
        from books.models import Chapter
        from django.db.models import Count

        counts = (
            Chapter.objects.filter(book_id__in=missing_book_ids, is_public=True)
            .values('book_id')
            .annotate(count=Count('id'))
        )

        counts_dict = {item['book_id']: item['count'] for item in counts}

        # Cache the fetched values
        to_cache = {}
        for book_id in missing_book_ids:
            count = counts_dict.get(book_id, 0)
            result[book_id] = count
            to_cache[f"book:{book_id}:chapter_count"] = count

        cache.set_many(to_cache, timeout=TIMEOUT_METADATA)

    return result


def get_cached_total_chapter_views_bulk(book_ids):
    """
    Get total chapter views for multiple books in one cache operation.

    Uses cache.get_many() for efficiency.

    Args:
        book_ids: List of book IDs

    Returns:
        dict: {book_id: total_views}
    """
    if not book_ids:
        return {}

    # Build cache keys
    cache_keys = [f"book:{book_id}:total_chapter_views" for book_id in book_ids]
    key_to_book_id = {f"book:{book_id}:total_chapter_views": book_id for book_id in book_ids}

    # Get from cache
    cached = cache.get_many(cache_keys)

    # Find missing keys
    result = {}
    missing_book_ids = []

    for cache_key, book_id in key_to_book_id.items():
        if cache_key in cached:
            result[book_id] = cached[cache_key]
        else:
            missing_book_ids.append(book_id)

    # Fetch missing from database
    if missing_book_ids:
        from books.models import ChapterStats
        from django.db.models import Sum

        views = (
            ChapterStats.objects.filter(chapter__book_id__in=missing_book_ids)
            .values('chapter__book_id')
            .annotate(total=Sum('view_count'))
        )

        views_dict = {item['chapter__book_id']: item['total'] or 0 for item in views}

        # Cache the fetched values
        to_cache = {}
        for book_id in missing_book_ids:
            total = views_dict.get(book_id, 0)
            result[book_id] = total
            to_cache[f"book:{book_id}:total_chapter_views"] = total

        cache.set_many(to_cache, timeout=TIMEOUT_METADATA)

    return result
```

#### Step 4.2: Update `reader/views/base.py` - `enrich_books_with_metadata()`

```python
def enrich_books_with_metadata(self, books, language_code):
    """
    Add published chapters count, total views, localized genres, and section to books.

    Uses bulk cached data to eliminate N+1 queries.
    """
    if not books:
        return []

    # Get all book IDs for bulk cache lookup
    book_ids = [book.id for book in books]

    # Bulk fetch chapter counts and views (2 cache operations instead of 24)
    chapter_counts = cache.get_cached_chapter_counts_bulk(book_ids)
    chapter_views = cache.get_cached_total_chapter_views_bulk(book_ids)

    enriched_books = []
    for book in books:
        # Use bulk-fetched data
        book.published_chapters_count = chapter_counts.get(book.id, 0)
        book.total_chapter_views = chapter_views.get(book.id, 0)

        # Add localized section name if section exists
        if hasattr(book.bookmaster, 'section') and book.bookmaster.section:
            book.section_localized_name = book.bookmaster.section.get_localized_name(language_code)
        else:
            book.section_localized_name = None

        # Add localized names to each genre (including parent)
        for genre in book.bookmaster.genres.all():
            genre.localized_name = genre.get_localized_name(language_code)
            if genre.parent:
                genre.parent_localized_name = genre.parent.get_localized_name(language_code)
            if genre.section:
                genre.section_localized_name = genre.section.get_localized_name(language_code)

        enriched_books.append(book)

    return enriched_books
```

---

## Testing Checklist

After implementing the fixes:

- [ ] Test StyleConfig caching:
  - [ ] Create a StyleConfig in admin, verify it's cached
  - [ ] Update StyleConfig, verify cache is invalidated
  - [ ] Delete StyleConfig, verify cache is invalidated

- [ ] Test BookDetailView optimization:
  - [ ] Use Django Debug Toolbar to verify only 1 chapter query
  - [ ] Verify chapter count, word count, and last_update are correct

- [ ] Test ChapterDetailView optimization:
  - [ ] Verify prev/next navigation works correctly
  - [ ] Use Django Debug Toolbar to verify only 1 query for both chapters

- [ ] Test bulk cache functions:
  - [ ] Verify book lists load with 2 cache operations instead of 24
  - [ ] Test cache miss scenario (first load after cache clear)
