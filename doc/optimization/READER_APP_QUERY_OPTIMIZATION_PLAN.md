# COMPREHENSIVE READER APP QUERY OPTIMIZATION PLAN

**Created:** 2025-11-27
**Status:** Planning
**Priority:** HIGH

---

## 📊 EXECUTIVE SUMMARY

This document outlines a comprehensive, generalized refactoring plan to systematically eliminate N+1 query problems across the entire reader app. The current implementation suffers from 70-85% excessive queries due to template tag N+1 issues, missing prefetches, and inconsistent query patterns.

**Current State:** 30-90 queries per page (with 60-85% duplicates)
**Target State:** 8-15 queries per page (minimal duplicates)
**Expected Impact:** 70-85% query reduction across all views

---

## 🔍 ANALYSIS SUMMARY

### Views Analyzed

1. ✅ **WelcomeView** - Homepage with featured books, recently updated, new arrivals
2. ✅ **SectionHomeView** - Section landing page with recent books
3. ✅ **SectionBookListView** - Filtered book lists with genre/tag/status
4. ✅ **BookSearchView** - Search with weighted keyword results
5. ✅ **SectionBookDetailView** - Book detail with chapter list
6. ✅ **SectionChapterDetailView** - Chapter reading view
7. ✅ **AuthorDetailView** - Author page with their books

### Common Query Problems Across ALL Views

| Problem | Affected Views | Current Impact | Root Cause |
|---------|---------------|----------------|------------|
| **1. Template tag N+1** | Welcome, SectionHome, BookList, Search, AuthorDetail | 3-20 queries per page | `enrich_book_meta` template tag queries `new_chapters_count` for each book |
| **2. Missing prefetches** | ALL book list views | 20-40 queries per page | `bookmaster__author`, `bookmaster__entities`, `bookstats`, `chapterstats_set` not prefetched |
| **3. Individual cache calls** | ALL views with books | 10-30 queries per page | `get_cached_chapter_count()` called per book instead of bulk |
| **4. Genre/tag queries** | BookList, Search | 5-15 queries per page | Not using prefetched data in enrichment |
| **5. Chapter queries in templates** | BookDetail | 3-5 queries | `.count()`, `.first()` called in view context building |

### Example: WelcomeView Debug Output

```
SQL queries from 1 connection
× default 92.99 ms (74 queries including 67 similar and 65 duplicates)

Key issues:
- SELECT ... FROM "books_language" WHERE code = 'zh-hans' - Duplicated 3 times
- SELECT ... FROM "books_genre" ... - Duplicated 2 times
- SELECT ... FROM "books_chapter" WHERE book_id = 1 - Duplicated 2 times per book
- SELECT ... FROM "books_bookstats" WHERE book_id = 1 - Duplicated 2 times per book
- SELECT ... FROM "books_chapterstats" ... - Duplicated 2 times per book
- SELECT ... FROM "reader_styleconfig" ... - Duplicated 10 times per section
```

---

## 🎯 GENERALIZED OPTIMIZATION STRATEGY

### Phase 1: Standardize Query Patterns (Foundation)

**Goal:** Create consistent, optimized querysets that ALL views can reuse.

#### 1.1 Create Optimized Queryset Managers

**File:** `myapp/books/models.py`

Add custom managers for consistent prefetching:

```python
# books/models.py

class BookQuerySet(models.QuerySet):
    """Optimized querysets for Book model."""

    def with_full_relations(self):
        """
        Standard prefetch for book list views.
        Eliminates N+1 for all book card rendering.

        Use this for:
        - Homepage carousels
        - Book list pages
        - Search results
        - Author book lists
        """
        return self.select_related(
            "bookmaster",
            "bookmaster__section",
            "bookmaster__author",
            "language",
            "bookstats",  # For views aggregation
        ).prefetch_related(
            "chapters",  # For filtering/counting
            "chapterstats_set",  # For view stats
            "bookmaster__genres",
            "bookmaster__genres__section",
            "bookmaster__genres__parent",  # For hierarchy
            "bookmaster__tags",
            "bookmaster__entities",
        )

    def for_list_display(self, language, section=None):
        """
        Optimized for list views with language/section filter.

        Use this for:
        - SectionHomeView
        - SectionBookListView
        - Search results

        Args:
            language: Language object
            section: Section object or None

        Returns:
            QuerySet with full relations prefetched
        """
        qs = self.filter(language=language, is_public=True)
        if section:
            qs = qs.filter(bookmaster__section=section)
        return qs.with_full_relations()

    def for_detail_display(self, language, slug, section=None):
        """
        Optimized for detail views.
        Includes chapter pagination support.

        Use this for:
        - SectionBookDetailView
        - BookDetailView (legacy)

        Args:
            language: Language object
            slug: Book slug
            section: Section object or None

        Returns:
            QuerySet with full relations prefetched
        """
        qs = self.filter(language=language, slug=slug, is_public=True)
        if section:
            qs = qs.filter(bookmaster__section=section)
        return qs.select_related(
            "bookmaster",
            "bookmaster__section",
            "bookmaster__author",
            "language",
            "bookstats",
        ).prefetch_related(
            "bookmaster__genres",
            "bookmaster__genres__section",
            "bookmaster__genres__parent",
            "bookmaster__tags",
            "bookmaster__entities",
            # Chapters prefetched separately with pagination
        )


class BookManager(models.Manager):
    """Custom manager for Book model with optimized querysets."""

    def get_queryset(self):
        return BookQuerySet(self.model, using=self._db)

    def with_full_relations(self):
        """Shortcut for with_full_relations()."""
        return self.get_queryset().with_full_relations()

    def for_list_display(self, language, section=None):
        """Shortcut for for_list_display()."""
        return self.get_queryset().for_list_display(language, section)

    def for_detail_display(self, language, slug, section=None):
        """Shortcut for for_detail_display()."""
        return self.get_queryset().for_detail_display(language, slug, section)


class Book(TimeStampedModel, SlugGeneratorMixin):
    # ... existing fields ...

    objects = BookManager()  # Replace default manager
```

**Impact:** Centralizes all prefetch logic, ensures consistency across views.

**Testing:**
```python
# In Django shell
python manage.py shell

from books.models import Book
from books.models import Language, Section

lang = Language.objects.get(code='en')
section = Section.objects.get(slug='fiction')

# Test list display queryset
books = Book.objects.for_list_display(lang, section)[:5]
print(len(books))  # Should prefetch all relations

# Verify no additional queries when accessing relations
book = books[0]
print(book.bookmaster.section.name)  # No query
print(book.bookmaster.author.name)  # No query
print([g.name for g in book.bookmaster.genres.all()])  # No query
```

---

### Phase 2: Fix Template Tag N+1 (HIGHEST PRIORITY)

**Goal:** Move `new_chapters_count` calculation to view layer using bulk queries.

#### 2.1 Add Bulk New Chapters Calculation to BaseReaderView

**File:** `myapp/reader/views/base.py`

Add new method after `enrich_book_with_metadata()`:

```python
# reader/views/base.py

def enrich_books_with_new_chapters(self, books, language_code):
    """
    Bulk calculate new chapters count for multiple books.
    Eliminates N+1 from enrich_book_meta template tag.

    This method runs ONE query for all books instead of one query per book.

    Args:
        books: List of Book objects
        language_code: Language code (for potential future localization)

    Returns:
        List of enriched books with new_chapters_count attribute
    """
    from django.utils import timezone
    from datetime import timedelta
    from django.conf import settings
    from django.db.models import Count, Q

    if not books:
        return books

    new_chapter_days = getattr(settings, 'NEW_CHAPTER_DAYS', 14)
    cutoff_date = timezone.now() - timedelta(days=new_chapter_days)

    # Get book IDs
    book_ids = [book.id for book in books]

    # Single bulk query with annotation
    # This replaces N queries with 1 query
    new_chapters_data = dict(
        Book.objects.filter(id__in=book_ids)
        .annotate(
            new_count=Count(
                'chapters',
                filter=Q(
                    chapters__is_public=True,
                    chapters__published_at__gte=cutoff_date
                )
            )
        )
        .values_list('id', 'new_count')
    )

    # Attach to books
    for book in books:
        book.new_chapters_count = new_chapters_data.get(book.id, 0)

    return books
```

#### 2.2 Integrate into enrich_books_with_metadata()

**File:** `myapp/reader/views/base.py`

Update existing method (around line 250-267):

```python
def enrich_books_with_metadata(self, books, language_code):
    """
    Add metadata to multiple books (list view helper).

    Now includes:
    - Chapter counts (bulk cached)
    - Total views (bulk cached)
    - New chapters count (bulk calculated) ← NEW
    - Localized taxonomy

    Args:
        books: Queryset or list of Book objects
        language_code: Language code for localization

    Returns:
        List of enriched book objects
    """
    if not books:
        return []

    # Convert to list if queryset
    books = list(books)

    # Bulk fetch chapter counts from cache
    book_ids = [book.id for book in books]
    chapter_counts = cache.get_cached_chapter_counts_bulk(book_ids)
    view_counts = cache.get_cached_total_chapter_views_bulk(book_ids)

    enriched_books = []
    for book in books:
        # Use bulk-fetched cached data
        book.published_chapters_count = chapter_counts.get(book.id, 0)
        book.total_chapter_views = view_counts.get(book.id, 0)

        # Continue with existing per-book enrichment (uses prefetched data)
        self.enrich_book_with_metadata(book, language_code)
        enriched_books.append(book)

    # NEW: Bulk calculate new chapters (eliminates template tag N+1)
    return self.enrich_books_with_new_chapters(enriched_books, language_code)
```

#### 2.3 Update Template Tag to Use Pre-calculated Data

**File:** `myapp/reader/templatetags/reader_extras.py`

Update existing tag (around line 642-676):

```python
@register.simple_tag
def enrich_book_meta(book):
    """
    Enrich book object with additional metadata.

    IMPORTANT: new_chapters_count is now pre-calculated in the view layer.
    This tag just returns pre-attached metadata without running queries.

    Before optimization: Ran 1 query per book (N+1 problem)
    After optimization: Returns pre-calculated data (0 queries)

    Args:
        book: Book object with pre-calculated metadata

    Returns:
        Dictionary with enriched metadata
    """
    # Get pre-calculated new_chapters_count or default to 0
    new_chapters_count = getattr(book, 'new_chapters_count', 0)

    return {
        'book': book,
        'new_chapters_count': new_chapters_count,
    }
```

**Impact:** Eliminates 3-20 queries per page on ALL book list views.

**Testing:**
1. Enable Django Debug Toolbar
2. Visit welcome page
3. Check SQL panel - should see ONE new chapters query for all books, not one per book
4. Verify "new chapters" badges still appear correctly on book cards

---

### Phase 3: Update All Cache Functions

**Goal:** Ensure all homepage cache functions use comprehensive prefetches.

#### 3.1 Standardize Homepage Cache Prefetches

**File:** `myapp/reader/cache/homepage.py`

Update ALL three functions:

```python
# reader/cache/homepage.py

def get_cached_featured_books(language_code, featured_bookmaster_ids):
    """
    Get featured books carousel from cache or database.

    Cache key: homepage:featured:{language_code}
    TTL: 10 minutes

    OPTIMIZED: Now uses Book.objects.with_full_relations()
    """
    if not featured_bookmaster_ids:
        return []

    cache_key = f"homepage:featured:{language_code}"
    books = cache.get(cache_key)

    if books is None:
        books = list(
            Book.objects.filter(
                bookmaster_id__in=featured_bookmaster_ids,
                language__code=language_code,
                is_public=True,
            )
            .with_full_relations()  # ← Use new manager method
        )
        cache.set(cache_key, books, timeout=TIMEOUT_HOMEPAGE)

    return books


def get_cached_recently_updated(language_code, limit=6):
    """
    Get recently updated books (by latest chapter) from cache or database.

    Cache key: homepage:recently_updated:{language_code}
    TTL: 10 minutes

    OPTIMIZED: Now uses Book.objects.with_full_relations()
    """
    cache_key = f"homepage:recently_updated:{language_code}"
    books = cache.get(cache_key)

    if books is None:
        from django.db.models import Max
        books = list(
            Book.objects.filter(language__code=language_code, is_public=True)
            .with_full_relations()  # ← Use new manager method
            .annotate(latest_chapter=Max("chapters__published_at"))
            .order_by("-latest_chapter")[:limit]
        )
        cache.set(cache_key, books, timeout=TIMEOUT_HOMEPAGE)

    return books


def get_cached_new_arrivals(language_code, limit=6):
    """
    Get recently published books from cache or database.

    Cache key: homepage:new_arrivals:{language_code}
    TTL: 10 minutes

    OPTIMIZED: Now uses Book.objects.with_full_relations()
    """
    cache_key = f"homepage:new_arrivals:{language_code}"
    books = cache.get(cache_key)

    if books is None:
        books = list(
            Book.objects.filter(language__code=language_code, is_public=True)
            .with_full_relations()  # ← Use new manager method
            .order_by("-published_at")[:limit]
        )
        cache.set(cache_key, books, timeout=TIMEOUT_HOMEPAGE)

    return books
```

**Impact:** Eliminates 20-30 queries per page on homepage and section home.

**Testing:**
1. Clear cache: `python manage.py shell -c "from django.core.cache import cache; cache.clear()"`
2. Visit homepage with Django Debug Toolbar
3. Check that genre/tag/entity queries are not duplicated
4. Verify cache is populated correctly

---

### Phase 4: Update ALL View Querysets

**Goal:** Replace manual queryset building with optimized manager methods.

#### 4.1 WelcomeView

**File:** `myapp/reader/views/general.py`

No changes needed - already uses cached functions which are optimized in Phase 3.

#### 4.2 SectionHomeView

**File:** `myapp/reader/views/section.py` (lines 47-66)

**Before:**
```python
def get_queryset(self):
    """Get recent books from this section"""
    language = self.get_language()
    section = self.get_section()

    if not section:
        raise Http404("Section required")

    queryset = Book.objects.filter(
        language=language,
        is_public=True,
        bookmaster__section=section
    )

    return (
        queryset.select_related("bookmaster", "bookmaster__section", "language")
        .prefetch_related("chapters", "bookmaster__genres", "bookmaster__genres__section", "bookmaster__tags")
        .order_by("-published_at", "-created_at")[:12]
    )
```

**After:**
```python
def get_queryset(self):
    """Get recent books from this section"""
    language = self.get_language()
    section = self.get_section()

    if not section:
        raise Http404("Section required")

    # Use optimized manager method
    return Book.objects.for_list_display(
        language=language,
        section=section
    ).order_by("-published_at", "-created_at")[:12]
```

#### 4.3 SectionBookListView

**File:** `myapp/reader/views/section.py` (lines 113-158)

**Before:**
```python
def get_queryset(self):
    language = self.get_language()
    section = self.get_section()

    if not section:
        raise Http404("Section required")

    queryset = Book.objects.filter(
        language=language,
        is_public=True,
        bookmaster__section=section
    )

    # Filter logic...

    return (
        queryset.select_related("bookmaster", "bookmaster__section", "language")
        .prefetch_related("chapters", "bookmaster__genres", "bookmaster__genres__section", "bookmaster__tags")
        .order_by("-published_at", "-created_at")
    )
```

**After:**
```python
def get_queryset(self):
    language = self.get_language()
    section = self.get_section()

    if not section:
        raise Http404("Section required")

    # Start with optimized base queryset
    queryset = Book.objects.for_list_display(language=language, section=section)

    # Apply filters (genre, tag, status)
    genre_slug = self.request.GET.get("genre")
    if genre_slug:
        genre = Genre.objects.filter(slug=genre_slug, section=section).first()
        if genre:
            bookmaster_ids = BookGenre.objects.filter(genre=genre).values_list(
                "bookmaster_id", flat=True
            )
            queryset = queryset.filter(bookmaster_id__in=bookmaster_ids)

    tag_slug = self.request.GET.get("tag")
    if tag_slug:
        tag = Tag.objects.filter(slug=tag_slug).first()
        if tag:
            from books.models import BookTag
            bookmaster_ids = BookTag.objects.filter(tag=tag).values_list(
                "bookmaster_id", flat=True
            )
            queryset = queryset.filter(bookmaster_id__in=bookmaster_ids)

    progress = self.request.GET.get("status")
    if progress and progress in ["draft", "ongoing", "completed"]:
        queryset = queryset.filter(progress=progress)

    return queryset.order_by("-published_at", "-created_at")
```

#### 4.4 BaseSearchView

**File:** `myapp/reader/views/base.py` (lines 416-420)

**Before:**
```python
return (
    queryset.select_related("bookmaster", "bookmaster__section", "language")
    .prefetch_related("chapters", "bookmaster__genres", "bookmaster__genres__section", "bookmaster__tags")
    .order_by("-published_at", "-created_at")
)
```

**After:**
```python
return queryset.with_full_relations().order_by("-published_at", "-created_at")
```

**Also update** (lines 452-456):

**Before:**
```python
queryset = Book.objects.filter(id__in=book_ids).select_related(
    "bookmaster", "bookmaster__section", "language"
).prefetch_related(
    "chapters", "bookmaster__genres", "bookmaster__genres__section", "bookmaster__tags"
)
```

**After:**
```python
queryset = Book.objects.filter(id__in=book_ids).with_full_relations()
```

#### 4.5 SectionBookDetailView

**File:** `myapp/reader/views/section.py` (lines 270-284)

**Before:**
```python
def get_queryset(self):
    """Get book queryset with section validation"""
    language = self.get_language()
    section = self.get_section()

    if not section:
        raise Http404("Section required")

    return (
        Book.objects.filter(
            language=language,
            is_public=True,
            bookmaster__section=section
        )
        .select_related("bookmaster", "bookmaster__section", "bookmaster__author", "language")
        .prefetch_related(
            "chapters__chaptermaster",
            "bookmaster__genres",
            "bookmaster__genres__parent",
            "bookmaster__genres__section",
            "bookmaster__tags"
        )
    )
```

**After:**
```python
def get_queryset(self):
    """Get book queryset with section validation"""
    language = self.get_language()
    section = self.get_section()

    if not section:
        raise Http404("Section required")

    # Use optimized manager method for detail views
    # Note: chapters are NOT prefetched here because we use pagination
    return Book.objects.for_detail_display(
        language=language,
        slug=self.kwargs.get('book_slug'),
        section=section
    )
```

#### 4.6 AuthorDetailView

**File:** `myapp/reader/views/general.py` (lines 274-281)

**Before:**
```python
books = list(
    Book.objects.filter(
        bookmaster__author=self.object, language=language, is_public=True
    )
    .select_related("bookmaster", "bookmaster__section", "language")
    .prefetch_related("bookmaster__genres", "bookmaster__genres__section")
    .order_by("-created_at")
)
```

**After:**
```python
books = list(
    Book.objects.filter(
        bookmaster__author=self.object,
        language=language,
        is_public=True
    )
    .with_full_relations()  # Use manager method
    .order_by("-created_at")
)
```

**Impact:** Ensures ALL views use consistent, optimized querysets.

---

### Phase 5: Optimize Book Detail View Context Building

**Goal:** Eliminate redundant queries in get_context_data().

#### 5.1 Fix SectionBookDetailView Context

**File:** `myapp/reader/views/section.py` (lines 300-357)

**Problem:** Currently runs multiple queries:
- `all_chapters.count()` - Line 333
- `sum(chapter.effective_count for chapter in all_chapters)` - Lines 334-336 (iterates all chapters)
- `all_chapters.order_by("-published_at").first()` - Line 339

**Before:**
```python
# Reading progress context (use all chapters for stats, not just current page)
context["total_chapters"] = all_chapters.count()
context["total_words"] = sum(
    chapter.effective_count for chapter in all_chapters
)

# Last update from most recently published chapter
latest_chapter = all_chapters.order_by("-published_at").first()
context["last_update"] = latest_chapter.published_at if latest_chapter else None
```

**After:**
```python
# OPTIMIZED: Use aggregate instead of count() + iteration
from django.db.models import Sum, Max, Count

stats = all_chapters.aggregate(
    total=Count('id'),
    total_words=Sum('word_count'),
    total_chars=Sum('character_count'),
    last_update=Max('published_at')
)

context["total_chapters"] = stats['total'] or 0

# Use language-appropriate count
if self.object.language.count_units == 'words':
    context["total_words"] = stats['total_words'] or 0
else:
    context["total_words"] = stats['total_chars'] or 0

context["last_update"] = stats['last_update']
```

**Impact:** Eliminates 3-5 queries on book detail page.

---

### Phase 6: Optimize enrich_book_with_metadata()

**Goal:** Ensure prefetched data is used, avoid triggering new queries.

#### 6.1 Update to Use Prefetched Data Explicitly

**File:** `myapp/reader/views/base.py` (lines 171-248)

Add explicit comments and safety checks:

```python
def enrich_book_with_metadata(self, book, language_code):
    """
    Add metadata to a single book.

    IMPORTANT: This method assumes book has prefetched relations.
    Always use Book.objects.with_full_relations() before calling this.

    Prefetch requirements:
    - bookmaster (select_related)
    - bookmaster__section (select_related)
    - bookmaster__author (select_related)
    - bookmaster__genres (prefetch_related)
    - bookmaster__genres__parent (prefetch_related)
    - bookmaster__genres__section (prefetch_related)
    - bookmaster__tags (prefetch_related)
    - bookmaster__entities (prefetch_related)

    Args:
        book: Book object with prefetched relations
        language_code: Language code for localization

    Returns:
        The enriched book object (modified in-place)
    """
    # Chapter count - use cached value (set by enrich_books_with_metadata bulk call)
    # For single-book enrichment (detail views), still use cache
    if not hasattr(book, 'published_chapters_count'):
        book.published_chapters_count = cache.get_cached_chapter_count(book.id)

    # Total views - use cached value (set by enrich_books_with_metadata bulk call)
    if not hasattr(book, 'total_chapter_views'):
        book.total_chapter_views = cache.get_cached_total_chapter_views(book.id)

    # Add localized section name (uses prefetched bookmaster.section)
    if hasattr(book.bookmaster, 'section') and book.bookmaster.section:
        book.section_localized_name = book.bookmaster.section.get_localized_name(language_code)
    else:
        book.section_localized_name = None

    # Add localized author name (uses prefetched bookmaster.author)
    if hasattr(book.bookmaster, 'author') and book.bookmaster.author:
        book.author_localized_name = book.bookmaster.author.get_localized_name(language_code)
    else:
        book.author_localized_name = None

    # CRITICAL: Use .all() to access prefetched data, don't trigger new query
    # The .all() method uses the prefetch cache if available
    genres = list(book.bookmaster.genres.all())
    for genre in genres:
        genre.localized_name = genre.get_localized_name(language_code)
        if genre.parent:  # Parent is prefetched via bookmaster__genres__parent
            genre.parent_localized_name = genre.parent.get_localized_name(language_code)
        if genre.section:  # Section is prefetched via bookmaster__genres__section
            genre.section_localized_name = genre.section.get_localized_name(language_code)
    book.enriched_genres = genres

    # Set primary genre for breadcrumb (first genre without parent)
    primary_genres = [g for g in genres if not g.parent]
    book.primary_genre = primary_genres[0] if primary_genres else None

    # Tags by category (uses prefetched bookmaster.tags)
    tags = list(book.bookmaster.tags.all())
    tags_by_category = {}
    for tag in tags:
        tag.localized_name = tag.get_localized_name(language_code)
        category = tag.category
        if category not in tags_by_category:
            tags_by_category[category] = []
        tags_by_category[category].append(tag)
    book.tags_by_category = tags_by_category

    # Entities by type (uses prefetched bookmaster.entities)
    entities = list(book.bookmaster.entities.exclude(order=999))
    entities_by_type = {}
    for entity in entities:
        # Get localized name from translations or fall back to source_name
        entity.localized_name = entity.translations.get(language_code, entity.source_name)
        entity_type_display = entity.get_entity_type_display()
        if entity_type_display not in entities_by_type:
            entities_by_type[entity_type_display] = []
        entities_by_type[entity_type_display].append(entity)
    book.entities_by_type = entities_by_type

    return book
```

**Impact:** Guarantees prefetched data usage, prevents accidental query triggers.

---

## 📈 EXPECTED IMPACT ACROSS ALL VIEWS

| View | Current Queries | After Optimization | Savings | Time Saved |
|------|----------------|-------------------|---------|------------|
| **WelcomeView** | 74 (65 dupes) | 10-12 | ~62 queries | ~60ms |
| **SectionHomeView** | 50-60 | 8-10 | ~50 queries | ~45ms |
| **SectionBookListView** | 60-80 | 10-15 | ~60 queries | ~55ms |
| **BookSearchView** | 70-90 | 12-15 | ~70 queries | ~65ms |
| **SectionBookDetailView** | 30-40 | 8-12 | ~25 queries | ~25ms |
| **AuthorDetailView** | 50-70 | 10-15 | ~55 queries | ~50ms |

**Overall Impact:**
- **Query Reduction:** 70-85% fewer queries
- **Time Reduction:** 40-65ms faster page loads
- **Cache Efficiency:** Better cache hit rates with bulk operations
- **Scalability:** Can handle 3-5x more concurrent users with same DB load

---

## 🔧 IMPLEMENTATION ROADMAP

### Week 1: Foundation (High Impact)

**Day 1-2: Phase 1 - Create BookQuerySet and BookManager**
- [ ] Add `BookQuerySet` class to `books/models.py`
- [ ] Add `BookManager` class to `books/models.py`
- [ ] Update `Book` model to use `BookManager`
- [ ] Run tests: `python manage.py test books`
- [ ] Test in shell: Verify prefetch works correctly

**Day 3-4: Phase 2 - Fix Template Tag N+1 (HIGHEST IMPACT)**
- [ ] Add `enrich_books_with_new_chapters()` to `reader/views/base.py`
- [ ] Update `enrich_books_with_metadata()` to use bulk calculation
- [ ] Update `enrich_book_meta` template tag to use pre-calculated data
- [ ] Test on WelcomeView with Django Debug Toolbar
- [ ] Verify new chapters badges still work correctly

**Day 5: Testing - Verify Template Tag Fix**
- [ ] Test WelcomeView
- [ ] Test SectionHomeView
- [ ] Test SectionBookListView
- [ ] Test BookSearchView
- [ ] Test AuthorDetailView
- [ ] Verify query count reduction with Django Debug Toolbar

### Week 2: Cache & Querysets (Medium-High Impact)

**Day 6-7: Phase 3 - Update All Cache Functions**
- [ ] Update `get_cached_featured_books()` in `reader/cache/homepage.py`
- [ ] Update `get_cached_recently_updated()` in `reader/cache/homepage.py`
- [ ] Update `get_cached_new_arrivals()` in `reader/cache/homepage.py`
- [ ] Clear cache and test: `python manage.py shell -c "from django.core.cache import cache; cache.clear()"`
- [ ] Test WelcomeView with Django Debug Toolbar

**Day 8-10: Phase 4 - Update All View Querysets**
- [ ] Update `SectionHomeView.get_queryset()` in `section.py`
- [ ] Update `SectionBookListView.get_queryset()` in `section.py`
- [ ] Update `BaseSearchView.get_queryset()` in `base.py`
- [ ] Update `SectionBookDetailView.get_queryset()` in `section.py`
- [ ] Update `AuthorDetailView` book query in `general.py`
- [ ] Test each view after updating

**Day 11: Testing - Verify Queryset Optimizations**
- [ ] Run full test suite: `python manage.py test reader`
- [ ] Manual testing of all views with Django Debug Toolbar
- [ ] Check for any broken functionality
- [ ] Performance benchmarking

### Week 3: Detail Views & Polish (Medium Impact)

**Day 12-13: Phase 5 - Optimize Book Detail Context**
- [ ] Update `SectionBookDetailView.get_context_data()` in `section.py`
- [ ] Replace `.count()` with aggregate query
- [ ] Replace iteration with aggregate query
- [ ] Replace `.first()` with aggregate Max
- [ ] Test book detail page with Django Debug Toolbar

**Day 14: Phase 6 - Final enrich_book_with_metadata Polish**
- [ ] Add explicit comments to `enrich_book_with_metadata()`
- [ ] Verify all `.all()` calls use prefetch cache
- [ ] Add safety checks for missing prefetches
- [ ] Document prefetch requirements

**Day 15: Full Regression Testing**
- [ ] Test all reader views with Django Debug Toolbar
- [ ] Test with different languages (en, zh-hans, ja)
- [ ] Test with different sections (fiction, bl, gl)
- [ ] Test with filters (genre, tag, status)
- [ ] Test pagination
- [ ] Test search functionality

### Week 4: Performance Testing & Monitoring

**Day 16-17: Load Testing**
- [ ] Set up load testing with `locust` or `django-silk`
- [ ] Test homepage with 100 concurrent users
- [ ] Test book list with 50 concurrent users
- [ ] Test book detail with 100 concurrent users
- [ ] Measure average response times

**Day 18: Production Monitoring Setup**
- [ ] Set up Django Debug Toolbar for staff users only
- [ ] Configure slow query logging (>50ms)
- [ ] Set up APM if available (New Relic, DataDog, etc.)
- [ ] Document performance baselines

**Day 19: Cache Tuning**
- [ ] Monitor cache hit rates with Redis CLI: `INFO stats`
- [ ] Adjust cache timeouts based on usage patterns
- [ ] Consider cache warming for popular content
- [ ] Document cache strategy

**Day 20: Documentation & Handoff**
- [ ] Update CLAUDE.md with new patterns
- [ ] Document manager methods usage
- [ ] Create "Adding New Views" guide
- [ ] Review this plan and mark as COMPLETE

---

## ✅ TESTING CHECKLIST

After each phase, test with Django Debug Toolbar enabled.

### Per-View Testing

For each view, verify:

#### WelcomeView (`/en/`)
- [ ] Total queries ≤ 12
- [ ] No duplicate queries
- [ ] Query time < 50ms
- [ ] Featured books carousel works
- [ ] Recently updated section works
- [ ] New arrivals section works
- [ ] New chapters badges appear correctly

#### SectionHomeView (`/en/fiction/`)
- [ ] Total queries ≤ 10
- [ ] No duplicate queries
- [ ] Query time < 50ms
- [ ] Recent books list works
- [ ] Section genres display correctly
- [ ] Section navigation works

#### SectionBookListView (`/en/fiction/books/`)
- [ ] Total queries ≤ 15
- [ ] No duplicate queries
- [ ] Query time < 50ms
- [ ] Pagination works (test page 2, 3)
- [ ] Genre filter works (`?genre=fantasy`)
- [ ] Tag filter works (`?tag=cultivation`)
- [ ] Status filter works (`?status=ongoing`)
- [ ] Combined filters work
- [ ] Book cards render correctly

#### BookSearchView (`/en/fiction/search/?q=cultivation`)
- [ ] Total queries ≤ 15
- [ ] No duplicate queries
- [ ] Query time < 100ms (search is slower)
- [ ] Search results appear
- [ ] Matched keywords shown
- [ ] Search time displayed
- [ ] Filter by genre works
- [ ] Filter by tag works
- [ ] Pagination works

#### SectionBookDetailView (`/en/fiction/book/reverend-insanity/`)
- [ ] Total queries ≤ 12
- [ ] No duplicate queries
- [ ] Query time < 50ms
- [ ] Book information displays correctly
- [ ] Chapter list displays correctly
- [ ] Chapter count is correct
- [ ] Total words is correct
- [ ] Last update is correct
- [ ] Pagination works (`?page=2`)
- [ ] Sort by latest works (`?sort=latest`)
- [ ] Sort by new works (`?sort=new`)
- [ ] Genres, tags, entities display correctly

#### SectionChapterDetailView (`/en/fiction/book/reverend-insanity/chapter-1/`)
- [ ] Total queries ≤ 10
- [ ] No duplicate queries
- [ ] Query time < 50ms
- [ ] Chapter content displays correctly
- [ ] Previous chapter link works
- [ ] Next chapter link works
- [ ] Chapter navigation works

#### AuthorDetailView (`/en/author/er-gen/`)
- [ ] Total queries ≤ 15
- [ ] No duplicate queries
- [ ] Query time < 50ms
- [ ] Author information displays correctly
- [ ] Author books list works
- [ ] Book cards render correctly
- [ ] Books from all sections appear

### Database Query Analysis

For each view, check Django Debug Toolbar SQL panel:

- [ ] **Total Queries:** Should be ≤ 15 for list views, ≤ 12 for detail views
- [ ] **Duplicate Queries:** Should be 0
- [ ] **Similar Queries:** Should be minimal (< 5)
- [ ] **Slow Queries:** None > 50ms
- [ ] **Query Time:** Total < 100ms

### Cache Analysis

Check Redis cache behavior:

```bash
# Connect to Redis
redis-cli

# Check cache keys
KEYS *homepage*
KEYS *chapter_count*
KEYS *languages*

# Check cache hit rate
INFO stats

# Monitor cache operations in real-time
MONITOR
```

Verify:
- [ ] Homepage sections are cached (3 keys: featured, recently_updated, new_arrivals)
- [ ] Chapter counts are cached per book
- [ ] Languages and sections are cached
- [ ] Cache hit rate > 80%

### Functional Testing

Verify no regressions:

- [ ] New chapters badges appear on books published in last 14 days
- [ ] Badge count matches actual new chapters count
- [ ] Book stats (views, chapters) are correct
- [ ] Genre badges appear correctly
- [ ] Tag badges appear correctly
- [ ] Entity information displays correctly
- [ ] Author links work
- [ ] Section navigation works
- [ ] Language switching works
- [ ] Mobile responsive works

### Performance Benchmarking

Use `django-silk` or `locust` for load testing:

```bash
# Install django-silk
pip install django-silk

# Add to INSTALLED_APPS and urls.py
# See: https://github.com/jazzband/django-silk

# Run load test with locust
locust -f tests/locustfile.py --host=http://localhost:8000
```

Target metrics:
- [ ] Homepage: 100 req/s with p95 < 200ms
- [ ] Book list: 50 req/s with p95 < 300ms
- [ ] Book detail: 100 req/s with p95 < 200ms
- [ ] Search: 20 req/s with p95 < 500ms

---

## 🎯 PRIORITY ORDER

If you need immediate impact, implement in this order:

1. **Phase 2** (Template Tag Fix) - **HIGHEST PRIORITY**
   - Saves 3-20 queries per view
   - Affects ALL book list views
   - Relatively easy to implement
   - Immediate, visible impact

2. **Phase 3** (Cache Functions)
   - Saves 20-30 queries on homepage
   - Affects most-viewed page
   - Easy to implement
   - High traffic impact

3. **Phase 1** (Queryset Manager)
   - Foundation for all other phases
   - Centralizes optimization logic
   - Makes future maintenance easier
   - Enables consistent patterns

4. **Phase 4** (View Querysets)
   - Ensures consistency across all views
   - Uses manager methods from Phase 1
   - Medium difficulty
   - Wide impact

5. **Phase 5** (Detail Context)
   - Optimizes detail views
   - Lower traffic than list views
   - Medium difficulty
   - Moderate impact

6. **Phase 6** (Enrichment Polish)
   - Final safety checks
   - Prevents future regressions
   - Documentation value
   - Low difficulty

---

## 📝 MAINTENANCE NOTES

### Adding New Views

When creating new views that display books:

**DO:**
```python
# For list views
class MyBookListView(BaseBookListView):
    def get_queryset(self):
        return Book.objects.for_list_display(
            language=self.get_language(),
            section=self.get_section()
        ).order_by('-created_at')

# For detail views
class MyBookDetailView(BaseBookDetailView):
    def get_queryset(self):
        return Book.objects.for_detail_display(
            language=self.get_language(),
            slug=self.kwargs['slug'],
            section=self.get_section()
        )
```

**DON'T:**
```python
# Avoid manual queryset building
queryset = Book.objects.filter(...)
    .select_related(...)  # Incomplete prefetches
    .prefetch_related(...)  # Might miss relations
```

### Adding New Book Relations

If you add new ForeignKey or ManyToMany fields to Book or BookMaster:

1. **Update `BookQuerySet.with_full_relations()`:**
   ```python
   def with_full_relations(self):
       return self.select_related(
           # ... existing fields ...
           "bookmaster__new_relation",  # ← Add here
       ).prefetch_related(
           # ... existing fields ...
           "bookmaster__new_many_to_many",  # ← Or here
       )
   ```

2. **Update `enrich_book_with_metadata()` if needed:**
   ```python
   # Add localization or processing for new relation
   new_items = list(book.bookmaster.new_many_to_many.all())
   for item in new_items:
       item.localized_name = item.get_localized_name(language_code)
   book.enriched_new_items = new_items
   ```

3. **Update cache functions if needed:**
   - Add to homepage cache if displayed on homepage
   - Add cache invalidation signal if data changes frequently

### Cache Invalidation

When models change, caches are automatically invalidated via signals in `books/signals/cache.py`.

If you add new cached data:

1. **Add cache function to `reader/cache/`:**
   ```python
   def get_cached_my_data(key):
       cache_key = f"my_data:{key}"
       data = cache.get(cache_key)
       if data is None:
           data = # ... fetch from database ...
           cache.set(cache_key, data, timeout=TIMEOUT_STATIC)
       return data
   ```

2. **Add invalidation signal:**
   ```python
   # In books/signals/cache.py
   @receiver(post_save, sender=MyModel)
   def invalidate_my_data_cache(sender, instance, **kwargs):
       cache.delete(f"my_data:{instance.id}")
   ```

### Debugging Query Issues

If you suspect N+1 queries:

1. **Enable Django Debug Toolbar:**
   ```python
   # settings.py
   if DEBUG:
       INSTALLED_APPS += ['debug_toolbar']
       MIDDLEWARE += ['debug_toolbar.middleware.DebugToolbarMiddleware']
       INTERNAL_IPS = ['127.0.0.1']
   ```

2. **Check SQL panel:**
   - Look for "Similar queries" and "Duplicate queries"
   - Click "Explain" to see query execution plan
   - Check if queries are using indexes

3. **Use `django-silk` for production:**
   ```bash
   pip install django-silk
   # Add to INSTALLED_APPS
   # Visit /silk/ to see profiling data
   ```

4. **Check prefetch cache usage:**
   ```python
   # In Django shell
   book = Book.objects.with_full_relations().first()

   # This should NOT trigger queries
   print(book.bookmaster.genres.all())
   print(book.bookmaster.tags.all())

   # Use django-debug-toolbar to verify
   ```

### Monitoring Cache Performance

Monitor cache hit rates regularly:

```bash
# Connect to Redis
redis-cli

# Check hit rate
INFO stats
# Look for: keyspace_hits, keyspace_misses

# Monitor real-time cache operations
MONITOR

# Check cache memory usage
INFO memory

# Check specific cache keys
KEYS *homepage*
TTL homepage:featured:en

# Clear cache if needed
FLUSHDB  # WARNING: Clears all cache
```

Target metrics:
- **Hit Rate:** > 80%
- **Memory Usage:** < 1GB
- **Eviction Rate:** < 5%

---

## 🚨 COMMON PITFALLS

### Pitfall 1: Forgetting to Use Manager Methods

**Bad:**
```python
books = Book.objects.filter(is_public=True, language=lang)
# Missing prefetches → N+1 queries
```

**Good:**
```python
books = Book.objects.for_list_display(language=lang)
# All prefetches included
```

### Pitfall 2: Accessing Related Objects Without Prefetch

**Bad:**
```python
for book in books:
    print(book.bookmaster.genres.all())  # N queries if not prefetched
```

**Good:**
```python
books = Book.objects.with_full_relations()
for book in books:
    print(book.bookmaster.genres.all())  # Uses prefetch cache, 0 queries
```

### Pitfall 3: Using .count() on Prefetched Relations

**Bad:**
```python
for book in books:
    count = book.chapters.filter(is_public=True).count()  # N queries
```

**Good:**
```python
# Use cached chapter counts
for book in books:
    count = cache.get_cached_chapter_count(book.id)  # 0 queries (cached)
```

### Pitfall 4: Not Using Bulk Operations

**Bad:**
```python
for book in books:
    cache.get(f"chapter_count:{book.id}")  # N cache round trips
```

**Good:**
```python
book_ids = [book.id for book in books]
counts = cache.get_cached_chapter_counts_bulk(book_ids)  # 1 cache round trip
```

### Pitfall 5: Template Tag Queries

**Bad:**
```python
@register.simple_tag
def get_new_chapters(book):
    return book.chapters.filter(published_at__gte=cutoff).count()
    # Called for each book → N queries
```

**Good:**
```python
# Calculate in view, pass to template
books = self.enrich_books_with_new_chapters(books, language_code)
# Template just displays: {{ book.new_chapters_count }}
```

---

## 📚 ADDITIONAL RESOURCES

### Django ORM Optimization

- [Django QuerySet API](https://docs.djangoproject.com/en/stable/ref/models/querysets/)
- [select_related vs prefetch_related](https://docs.djangoproject.com/en/stable/ref/models/querysets/#select-related)
- [Database access optimization](https://docs.djangoproject.com/en/stable/topics/db/optimization/)

### Tools

- [Django Debug Toolbar](https://django-debug-toolbar.readthedocs.io/)
- [django-silk](https://github.com/jazzband/django-silk) - Profiling
- [nplusone](https://github.com/jmcarp/nplusone) - Detect N+1 queries
- [django-querycount](https://github.com/bradmontgomery/django-querycount) - Count queries per request

### Performance Testing

- [Locust](https://locust.io/) - Load testing
- [Apache Bench](https://httpd.apache.org/docs/2.4/programs/ab.html) - Simple load testing
- [Django Performance Tips](https://docs.djangoproject.com/en/stable/topics/performance/)

---

## 📊 TRACKING PROGRESS

Use this checklist to track implementation:

### Phase 1: Foundation
- [ ] BookQuerySet implemented
- [ ] BookManager implemented
- [ ] Book model updated
- [ ] Tests passing
- [ ] Shell verification completed

### Phase 2: Template Tag Fix
- [ ] enrich_books_with_new_chapters() added
- [ ] enrich_books_with_metadata() updated
- [ ] Template tag updated
- [ ] Django Debug Toolbar verification
- [ ] Functional testing completed

### Phase 3: Cache Functions
- [ ] get_cached_featured_books() updated
- [ ] get_cached_recently_updated() updated
- [ ] get_cached_new_arrivals() updated
- [ ] Cache cleared and tested
- [ ] Django Debug Toolbar verification

### Phase 4: View Querysets
- [ ] SectionHomeView updated
- [ ] SectionBookListView updated
- [ ] BaseSearchView updated
- [ ] SectionBookDetailView updated
- [ ] AuthorDetailView updated
- [ ] All views tested

### Phase 5: Detail Context
- [ ] SectionBookDetailView.get_context_data() updated
- [ ] Aggregate queries implemented
- [ ] Django Debug Toolbar verification
- [ ] Functional testing completed

### Phase 6: Enrichment Polish
- [ ] Comments added to enrich_book_with_metadata()
- [ ] Safety checks added
- [ ] Documentation updated
- [ ] Code review completed

### Week 4: Monitoring
- [ ] Load testing completed
- [ ] Production monitoring setup
- [ ] Cache tuning completed
- [ ] Documentation finalized

---

## ✅ SIGN-OFF

When implementation is complete, verify:

- [ ] All tests passing (`python manage.py test`)
- [ ] Query count reduced by 70-85%
- [ ] Page load time reduced by 40-65ms
- [ ] No functional regressions
- [ ] Documentation updated
- [ ] Team trained on new patterns
- [ ] Production monitoring in place

**Implementation Status:** ⏳ Planning
**Last Updated:** 2025-11-27
**Next Review:** [Date after Week 1]

---

**End of Document**
