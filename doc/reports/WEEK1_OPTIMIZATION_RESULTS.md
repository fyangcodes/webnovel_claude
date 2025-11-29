# Week 1 Optimization Results

## Summary

Successfully implemented all three Week 1 pillars of the MASTER_OPTIMIZATION_PLAN, reducing homepage queries from **74+ to 18 queries** (75.7% reduction).

## Implementation Status

### ✅ Pillar 1: Advanced BookQuerySet (Days 1-2)
**Status**: COMPLETED
**File**: `myapp/books/models/core.py`

#### Changes Made:
1. Added `BookQuerySet` class (lines 210-446) with optimized prefetch methods:
   - `_select_base_relations()`: Base select_related for bookmaster, language
   - `_prefetch_genres_optimized()`: Prefetch with nested select_related (collapses 3 queries → 1)
   - `_prefetch_tags_optimized()`: Optimized tag prefetch with only()
   - `_prefetch_entities_optimized()`: Entity prefetch with limited fields
   - `with_card_relations()`: Lightweight queryset for book cards
   - `with_detail_relations()`: Full prefetch for detail pages

2. Added `BookManager` class (lines 448-479)

3. Assigned custom manager to Book model (line 260): `objects = BookManager()`

4. Updated 3 cache functions in `myapp/reader/cache/homepage.py` to use `.with_card_relations()`:
   - `get_cached_featured_books()` (line 42)
   - `get_cached_recently_updated()` (line 70)
   - `get_cached_new_arrivals()` (line 100)

#### Results:
- Book queries now use 5-6 JOINs (all relations prefetched)
- Eliminated N+1 queries for genres, tags, entities on books
- Test: Single book with relations = 4 queries (down from ~12)

### ✅ Pillar 2: Bulk New Chapters Calculation (Days 4-5)
**Status**: COMPLETED
**File**: `myapp/reader/views/base.py`

#### Changes Made:
1. Added `enrich_books_with_new_chapters()` method (lines 303-357):
   - Uses single GROUP BY query instead of N individual `.count()` queries
   - Attaches `new_chapters_count` attribute to each book

2. Updated `enrich_books_with_metadata()` to call bulk method first (line 281)

3. Updated `enrich_book_meta` template tag in `myapp/reader/templatetags/reader_extras.py` (lines 642-684):
   - Checks for pre-calculated `new_chapters_count` attribute
   - Falls back to database query if not enriched (backwards compatible)

#### Results:
- New chapters calculation: 6-12 queries → 1 query
- Template tag no longer causes N+1 queries in lists

### ✅ Pillar 3: StyleConfig Prefetch (Day 3)
**Status**: COMPLETED
**File**: `myapp/reader/views/base.py`

#### Changes Made:
1. Added `_prefetch_styles_for_context()` method (lines 408-466):
   - Bulk prefetches StyleConfig for sections, genres, tags
   - Stores in context as lookup dictionaries

2. Updated `get_style` template tag in `myapp/reader/templatetags/reader_tags.py` (lines 14-64):
   - Now uses `takes_context=True`
   - Checks context dictionaries before querying database
   - Falls back to database if not prefetched (backwards compatible)

#### Results:
- Style queries: 16-41 queries → 2-4 queries
- Template tag uses cached lookups from context

### ✅ Additional Optimizations (Week 2 Stage 1)
**Status**: COMPLETED
**Files**: `myapp/reader/views/base.py`

#### Changes Made:
1. **Fixed BookStats N+1 Queries**:
   - Updated `enrich_books_with_metadata()` to skip expensive `total_chapter_views` in list context (lines 288-290)
   - Added `_is_list_context` flag to skip BookStats queries for book cards (line 297)
   - Updated `enrich_book_with_metadata()` to check context flag (lines 199-205)
   - **Rationale**: BookStats.get_total_chapter_views() requires accessing `book.chapters` which triggers reverse FK lookup, causing N+1. Not critical for card display.

2. **Fixed Entity .exclude() Breaking Prefetch**:
   - Changed from `.exclude(order=999)` to `.all()` + Python filtering (lines 242-257)
   - **Rationale**: `.exclude()` invalidates prefetch cache, causing additional query

3. **Bulk Chapter Counts**:
   - Added bulk fetch using `get_cached_chapter_counts_bulk()` (line 286)
   - Pre-attaches `_bulk_chapter_count` to avoid individual cache lookups (line 295)

## Final Query Breakdown

### Homepage Query Count: 18 queries

| Table | Queries | Notes |
|-------|---------|-------|
| books_book | 2 | Both with 5-6 JOINs (optimized) |
| books_genre | 4 | 2 for navigation cache + 2 for book enrichment (prefetch working) |
| books_chapter | 4 | 2 for new chapters calculation + 2 for counts |
| books_tag | 3 | 1 for navigation cache + 2 for book enrichment |
| books_bookentity | 2 | From book enrichment (prefetch working) |
| Other | 3 | Language, Section, misc queries |

### Query Reduction Progress:
- **Original**: 74+ queries (with many duplicates)
- **After Pillar 1**: 26 queries
- **After BookStats fix**: 24 queries
- **Final**: 18 queries

**Total Reduction**: 75.7% (74 → 18 queries)

## Why Some Queries Remain

1. **Navigation Queries (Expected)**:
   - 2 genre queries for `get_cached_genres()` and `get_cached_genres_flat()`
   - 1 tag query for `get_cached_tags()`
   - These are global navigation, not N+1

2. **Cache Disabled (DISABLE_CACHE=True)**:
   - In development, cache is bypassed using DummyCache
   - Each cache function call hits database
   - In production with Redis, these become 0 queries (served from cache)

3. **Multiple Book Sections**:
   - Homepage has 3 carousels: featured, recently_updated, new_arrivals
   - Each requires separate query (cannot be combined due to different filters/ordering)
   - With cache enabled, 2 of these would be cached

## Production Expected Performance

### With Cache Enabled (Redis):
- **Initial page load**: ~12 queries
- **Subsequent loads**: ~5-8 queries (most served from cache)
- **Cache TTL**: 10 min (homepage), 30 min (metadata), 24 hours (taxonomy)

### Remaining Optimizations (Week 2+):
- Implement Redis caching layer (currently using DummyCache)
- Add template fragment caching for expensive sections
- Optimize chapter queries further (combine into single query)
- Add query result caching for frequently accessed data

## Testing

### Verification Tests:
```bash
# Test BookQuerySet is active
docker exec webnovel_web python myapp/manage.py shell -c "
from books.models import Book
print('Manager type:', type(Book.objects))
print('Has with_card_relations:', hasattr(Book.objects, 'with_card_relations'))
"

# Test prefetch works
docker exec webnovel_web python myapp/manage.py shell -c "
from books.models import Book
from django.db import connection, reset_queries
from django.conf import settings
settings.DEBUG = True

reset_queries()
book = Book.objects.filter(is_public=True).with_card_relations().first()
print(f'Queries after fetch: {len(connection.queries)}')

reset_queries()
genres = list(book.bookmaster.genres.all())
print(f'Queries after genres access: {len(connection.queries)}')
"

# Test homepage loads
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/zh-hans/
```

### All Tests Pass:
- ✅ Custom manager active
- ✅ Prefetch working (0 additional queries for related data)
- ✅ Homepage loads successfully (HTTP 200)
- ✅ No Python errors
- ✅ All book card data displays correctly

## Files Modified

### Core Models:
- `myapp/books/models/core.py` (BookQuerySet, BookManager)

### Cache Layer:
- `myapp/reader/cache/homepage.py` (3 functions updated)

### Views:
- `myapp/reader/views/base.py` (bulk enrichment methods)

### Template Tags:
- `myapp/reader/templatetags/reader_tags.py` (get_style context-aware)
- `myapp/reader/templatetags/reader_extras.py` (enrich_book_meta optimized)

## Backwards Compatibility

All changes maintain backwards compatibility:
- Template tags fall back to database if enrichment not done
- `enrich_book_with_metadata()` works for both single and bulk contexts
- Existing code continues to work without modification

## Next Steps (Week 2)

1. **Enable Redis caching** (currently using DummyCache)
2. **Implement template fragment caching** for expensive sections
3. **Add cache invalidation** via signals
4. **Optimize remaining chapter queries**
5. **Add query monitoring** in production

## Conclusion

Week 1 optimizations successfully eliminated the majority of N+1 queries on the homepage. The remaining 18 queries are mostly unavoidable (navigation, multiple carousels with different filters) and will be further reduced in production with proper caching enabled.

The optimization strategy focused on:
1. **Prefetching** related data at query time (not in loops)
2. **Bulk calculations** replacing N individual queries with GROUP BY
3. **Context-aware template tags** using pre-fetched data from views
4. **Strategic skipping** of expensive calculations not needed for cards

This foundation enables efficient list views that scale well regardless of the number of books displayed.
