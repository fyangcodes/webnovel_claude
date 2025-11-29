# READER APP QUERY OPTIMIZATION PLAN V2 (IMPROVED)

**Created:** 2025-11-27
**Updated:** 2025-11-28 (incorporating advanced analysis)
**Status:** Planning
**Priority:** HIGH

---

## 🎯 WHAT'S NEW IN V2

This version incorporates **advanced query pattern analysis** that identifies:

1. ⚡ **Prefetch objects with select_related** - Collapses 3 queries → 1
2. ⚡ **OneToOne stats optimization** - Fix incorrect `chapterstats_set` usage
3. ⚡ **Deduplicated prefetch logic** - DRY helper methods
4. ⚡ **Context-specific querysets** - Lighter `with_card_relations()` for homepage
5. ⚡ **Memory optimization with only()** - 60% memory reduction

**Expected improvement over V1:** Additional 15-20% query reduction + 60% memory savings

---

## 📊 EXECUTIVE SUMMARY

**Current State:** 30-90 queries per page (with 60-85% duplicates)
**V1 Target:** 8-15 queries per page
**V2 Target:** 5-10 queries per page ← **IMPROVED**
**Expected Impact:** 85-92% query reduction + 60% memory savings

---

## 🔍 NEW INSIGHTS FROM ADVANCED ANALYSIS

### Critical Discovery #1: Nested Prefetch Creates 3X Queries

**Current approach:**
```python
.prefetch_related(
    "bookmaster__genres",
    "bookmaster__genres__section",
    "bookmaster__genres__parent",
)
```

This creates **3 separate queries**:
1. Query for genres
2. Query for sections
3. Query for parents

**Optimized approach:**
```python
Prefetch(
    "bookmaster__genres",
    queryset=Genre.objects.select_related("section", "parent")
)
```

This creates **1 multi-join query**.

**Impact:** 3 queries → 1 query per prefetch relation

---

### Critical Discovery #2: ChapterStats is OneToOne, Not M2M

**Current (WRONG):**
```python
.prefetch_related("chapterstats_set")  # ❌ This is wrong
```

**From codebase validation:**
```python
# books/models/stat.py:94-99
class ChapterStats(TimeStampModel):
    chapter = models.OneToOneField(
        "Chapter",
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="stats",  # ← The correct accessor
    )
```

**Correct approach:**
```python
# In chapter prefetch
Prefetch(
    "chapters",
    queryset=Chapter.objects.select_related("stats")  # ✅ Correct
)
```

**Impact:** Eliminates incorrect prefetch, reduces queries

---

### Critical Discovery #3: Homepage Loads Too Much Data

**Current:**
- `with_full_relations()` loads chapters + chapter stats
- Homepage book cards don't display chapter details
- Wasted bandwidth and memory

**Optimized:**
- New `with_card_relations()` method for homepage
- Excludes chapters and chapter stats
- 60% less data loaded

**Impact:** Homepage query count: 7 → 5 queries

---

## 🚀 REVISED OPTIMIZATION STRATEGY

### Phase 1: Advanced BookQuerySet Implementation (REVISED)

**Refer to:** `OPTIMIZED_BOOK_QUERYSET.py` for complete implementation

#### Key Improvements:

1. **Helper Methods for Reusable Prefetches:**
```python
def _prefetch_genres_optimized(self):
    """Collapses 3 queries → 1"""
    return Prefetch(
        "bookmaster__genres",
        queryset=Genre.objects.select_related("section", "parent")
    )

def _prefetch_tags_optimized(self):
    """Reduces memory with only()"""
    return Prefetch(
        "bookmaster__tags",
        queryset=Tag.objects.only("id", "name", "slug", "category", "translations")
    )
```

2. **Context-Specific Querysets:**
```python
def with_card_relations(self):
    """Lightweight for homepage/lists - NO chapters"""
    return self._select_base_relations().prefetch_related(
        self._prefetch_genres_optimized(),
        self._prefetch_tags_optimized(),
        self._prefetch_entities_optimized(),
    )

def with_full_relations(self):
    """Full prefetch including chapters for special cases"""
    return self.with_card_relations().prefetch_related(
        self._prefetch_chapters_with_stats(),
    )
```

3. **Fixed Stats Relationships:**
```python
# BookStats is select_related (OneToOne)
.select_related("bookstats")

# ChapterStats is accessed via chapter.stats (not chapterstats_set)
Prefetch(
    "chapters",
    queryset=Chapter.objects.select_related("stats", "chaptermaster")
)
```

**Complete implementation:** See [OPTIMIZED_BOOK_QUERYSET.py](OPTIMIZED_BOOK_QUERYSET.py)

---

### Phase 2-6: Same as V1

(Refer to original plan for Phases 2-6 - no changes)

---

## 📈 REVISED EXPECTED IMPACT

### Query Count Comparison

| View | Current | V1 Target | V2 Target | V2 Savings |
|------|---------|-----------|-----------|------------|
| **WelcomeView** | 74 (65 dupes) | 10-12 | **5-7** | **~68 queries** |
| **SectionHomeView** | 50-60 | 8-10 | **5-7** | **~53 queries** |
| **SectionBookListView** | 60-80 | 10-15 | **6-10** | **~70 queries** |
| **BookSearchView** | 70-90 | 12-15 | **8-12** | **~78 queries** |
| **SectionBookDetailView** | 30-40 | 8-12 | **6-10** | **~30 queries** |
| **AuthorDetailView** | 50-70 | 10-15 | **6-10** | **~60 queries** |

**Overall:** **85-92% query reduction** (improved from 70-85%)

### Memory Usage Comparison

**Before (without only()):**
- Each Tag: ~15 fields × 50 tags = 750 field values
- Each Entity: ~12 fields × 30 entities = 360 field values
- **Total: ~1100 fields per page**

**After (with only()):**
- Each Tag: ~5 fields × 50 tags = 250 field values
- Each Entity: ~6 fields × 30 entities = 180 field values
- **Total: ~430 fields per page**

**Memory Savings: 60% reduction**

---

## 🔧 IMPLEMENTATION UPDATES

### Week 1: Advanced QuerySet (Replaces V1 Phase 1)

**Day 1-2: Implement Optimized BookQuerySet**
- [ ] Copy code from `OPTIMIZED_BOOK_QUERYSET.py`
- [ ] Add to `books/models/core.py`
- [ ] Update Book model: `objects = BookManager()`
- [ ] Run tests: `python manage.py test books`

**Day 3: Update Homepage Cache Functions**
- [ ] Update `get_cached_featured_books()`: Use `.with_card_relations()`
- [ ] Update `get_cached_recently_updated()`: Use `.with_card_relations()`
- [ ] Update `get_cached_new_arrivals()`: Use `.with_card_relations()`
- [ ] Clear cache: `python manage.py shell -c "from django.core.cache import cache; cache.clear()"`

**Day 4-5: Template Tag Fix (Same as V1 Phase 2)**
- [ ] Add `enrich_books_with_new_chapters()` to base.py
- [ ] Update `enrich_books_with_metadata()` to use bulk calculation
- [ ] Update `enrich_book_meta` template tag
- [ ] Test with Django Debug Toolbar

### Week 2: View Updates (Same as V1)

Continue with V1 Phases 3-6...

---

## ✅ V2-SPECIFIC TESTING

### Query Count Targets (UPDATED)

After V2 implementation:

- [ ] **WelcomeView:** ≤ 7 queries (was 12)
- [ ] **SectionHomeView:** ≤ 7 queries (was 10)
- [ ] **SectionBookListView:** ≤ 10 queries (was 15)
- [ ] **BookSearchView:** ≤ 12 queries (was 15)
- [ ] **SectionBookDetailView:** ≤ 10 queries (was 12)

### Prefetch Validation

Verify Prefetch objects work correctly:

```python
# In Django shell
from books.models import Book
from django.db import connection
from django.test.utils import override_settings

# Enable query logging
@override_settings(DEBUG=True)
def test_prefetch():
    connection.queries_log.clear()

    # Test card relations
    books = list(Book.objects.with_card_relations()[:5])

    # Access relations (should not trigger queries)
    for book in books:
        _ = list(book.bookmaster.genres.all())
        _ = list(book.bookmaster.tags.all())
        _ = list(book.bookmaster.entities.all())

    # Check query count
    print(f"Total queries: {len(connection.queries)}")
    print("Queries:")
    for q in connection.queries:
        print(f"  {q['sql'][:100]}...")

    # Should see only 4-5 queries, not 15+
    assert len(connection.queries) <= 5

test_prefetch()
```

### Memory Usage Validation

Check field loading with only():

```python
# In Django shell
from books.models import Book
from sys import getsizeof

# Without only()
books_full = list(Book.objects.all()[:10].prefetch_related("bookmaster__tags"))
tags_full = [tag for book in books_full for tag in book.bookmaster.tags.all()]

# With only()
books_optimized = list(Book.objects.with_card_relations()[:10])
tags_optimized = [tag for book in books_optimized for tag in book.bookmaster.tags.all()]

print(f"Full tags memory: {getsizeof(tags_full)} bytes")
print(f"Optimized tags memory: {getsizeof(tags_optimized)} bytes")
print(f"Savings: {(1 - getsizeof(tags_optimized)/getsizeof(tags_full)) * 100:.1f}%")
```

---

## 🚨 V2-SPECIFIC PITFALLS

### Pitfall 1: Using chapterstats_set Instead of stats

**Bad:**
```python
for chapter in book.chapters.all():
    print(chapter.chapterstats_set.all())  # ❌ Wrong accessor name
```

**Good:**
```python
for chapter in book.chapters.all():
    print(chapter.stats)  # ✅ Correct (OneToOne field)
```

### Pitfall 2: Using with_full_relations() for Homepage

**Bad:**
```python
# Homepage doesn't need chapters
books = Book.objects.with_full_relations()  # ❌ Loads unnecessary data
```

**Good:**
```python
# Use lighter queryset for cards
books = Book.objects.with_card_relations()  # ✅ Only card data
```

### Pitfall 3: Not Using Prefetch Objects for Nested Relations

**Bad:**
```python
.prefetch_related(
    "bookmaster__genres",
    "bookmaster__genres__section",  # ❌ Creates extra query
)
```

**Good:**
```python
Prefetch(
    "bookmaster__genres",
    queryset=Genre.objects.select_related("section")  # ✅ Single query
)
```

---

## 📊 SQL QUERY COMPARISON

### Before V2:
```sql
-- Homepage with 6 books generates 74 queries:

-- Languages (duplicated 3 times)
SELECT * FROM books_language WHERE code = 'zh-hans';
SELECT * FROM books_language WHERE code = 'zh-hans';
SELECT * FROM books_language WHERE code = 'zh-hans';

-- Genres (3 queries per book × 6 books = 18 queries)
SELECT * FROM books_genre WHERE bookmaster_id IN (1,2,3,4,5,6);
SELECT * FROM books_section WHERE id IN (1,2,3);
SELECT * FROM books_genre WHERE id IN (7,8,9);  -- parents

-- Tags (1 query per book × 6 books = 6 queries)
SELECT * FROM books_tag INNER JOIN books_booktag ON ...;
SELECT * FROM books_tag INNER JOIN books_booktag ON ...;
...

-- Entities (1 query per book × 6 books = 6 queries)
SELECT * FROM books_bookentity WHERE bookmaster_id = 1;
SELECT * FROM books_bookentity WHERE bookmaster_id = 2;
...

Total: 74 queries
```

### After V2:
```sql
-- Homepage with 6 books generates 5-7 queries:

-- Books with select_related (1 query with multiple JOINs)
SELECT * FROM books_book
  LEFT OUTER JOIN books_bookmaster ON ...
  LEFT OUTER JOIN books_section ON ...
  LEFT OUTER JOIN books_author ON ...
  LEFT OUTER JOIN books_language ON ...
  LEFT OUTER JOIN books_bookstats ON ...
WHERE language_code = 'zh-hans' AND is_public = TRUE;

-- Genres with nested select_related (1 query)
SELECT * FROM books_genre
  LEFT OUTER JOIN books_section ON ...
  LEFT OUTER JOIN books_genre parent ON ...
WHERE bookmaster_id IN (1,2,3,4,5,6);

-- Tags with only() (1 query)
SELECT id, name, slug, category, translations
FROM books_tag
INNER JOIN books_booktag ON ...
WHERE bookmaster_id IN (1,2,3,4,5,6);

-- Entities with only() (1 query)
SELECT id, bookmaster_id, source_name, translations, entity_type, order
FROM books_bookentity
WHERE bookmaster_id IN (1,2,3,4,5,6) AND NOT (order = 999);

-- New chapters bulk calculation (1 query)
SELECT book_id, COUNT(*) FROM books_chapter
WHERE book_id IN (1,2,3,4,5,6)
  AND is_public = TRUE
  AND published_at >= '2025-11-14'
GROUP BY book_id;

-- Cache bulk get (0 SQL queries, 2 Redis round trips)
-- - Chapter counts: cache.get_many([...])
-- - View counts: cache.get_many([...])

Total: 5 queries + 2 Redis calls
```

**Improvement: 74 → 5 queries (93% reduction)**

---

## 📚 ADDITIONAL V2 RESOURCES

### Understanding Prefetch Objects

Django documentation:
- [Prefetch objects](https://docs.djangoproject.com/en/stable/ref/models/querysets/#prefetch-objects)
- [select_related](https://docs.djangoproject.com/en/stable/ref/models/querysets/#select-related)
- [prefetch_related](https://docs.djangoproject.com/en/stable/ref/models/querysets/#prefetch-related)

### Query Optimization Tools

- [django-querycount](https://github.com/bradmontgomery/django-querycount) - Middleware to print query count
- [nplusone](https://github.com/jmcarp/nplusone) - Detect N+1 queries automatically
- [django-silk](https://github.com/jazzband/django-silk) - Live profiling with visual query analysis

---

## 🎯 MIGRATION PATH FROM V1 TO V2

If you've already started V1 implementation:

1. **Replace BookQuerySet class:**
   - Keep your Phase 2 (template tag fix)
   - Replace Phase 1 with V2 advanced queryset
   - Update cache functions to use `.with_card_relations()`

2. **Fix stats relationships:**
   - Search for `chapterstats_set` in codebase
   - Replace with `chapter.stats` (OneToOne accessor)

3. **Update homepage caching:**
   - Change `with_full_relations()` → `with_card_relations()`
   - Homepage doesn't need chapters

4. **Test incrementally:**
   - Test each queryset method in Django shell
   - Verify query counts with Django Debug Toolbar
   - Check memory usage with `sys.getsizeof()`

---

## ✅ V2 SIGN-OFF CHECKLIST

When V2 implementation is complete:

- [ ] All tests passing (`python manage.py test`)
- [ ] Query count reduced by 85-92% (was 70-85%)
- [ ] Memory usage reduced by 60%
- [ ] Homepage ≤ 7 queries (was 74)
- [ ] Book lists ≤ 10 queries (was 60-80)
- [ ] Detail views ≤ 10 queries (was 30-40)
- [ ] No functional regressions
- [ ] Prefetch validation passed (shell tests)
- [ ] Memory validation passed (getsizeof tests)
- [ ] Documentation updated
- [ ] Team trained on new patterns
- [ ] Production monitoring in place

**Implementation Status:** ⏳ Planning
**Last Updated:** 2025-11-28
**Version:** V2 (Advanced)

---

**End of Document**
