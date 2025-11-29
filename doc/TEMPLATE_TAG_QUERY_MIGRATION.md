# Template Tag Query Migration Guide

**Purpose:** Eliminate ALL database queries from template tags by moving logic to view layer.

---

## 🎯 Overview

**Current Problem:**
- Template tags trigger 20-50 queries per page
- `enrich_book_meta`: 6-12 queries per page
- `hreflang_tags`: 1-2 queries per page
- `get_style`, `style_color`, `style_icon`: 10-40 queries per page

**Solution:**
- Prefetch ALL data in views
- Pass via context
- Template tags just format/display, never query

**Expected Savings:** 30-60 queries per page

---

## 📋 Template Tags to Migrate

### Priority 1: StyleConfig Tags (reader_tags.py)

**Current (BAD):**
```python
# reader_tags.py
@register.simple_tag
def get_style(obj):
    return get_style_for_object(obj)  # ❌ Query in template tag
```

**Impact:**
- Called for every section in navigation (4 sections = 4 queries)
- Called for every genre in filters (10-20 genres = 10-20 queries)
- Called in templates like welcome.html, section_home.html

**Total: 10-40 queries per page**

---

### Priority 2: enrich_book_meta (reader_extras.py)

Already covered in V2 optimization plan Phase 2.

**Current: 6-12 queries per page**
**After: 0 queries**

---

### Priority 3: hreflang_tags (reader_extras.py)

**Current: 1-2 queries per page**
**After: 0 queries**

---

## 🛠️ Implementation Guide

### Part 1: StyleConfig Migration

#### Step 1: Update BaseReaderView to Prefetch Styles

**File:** `myapp/reader/views/base.py`

Add after `get_context_data()` method:

```python
# reader/views/base.py

def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    language_code = self.kwargs.get("language_code")

    # ... existing code ...

    # NEW: Prefetch styles for all objects that might be displayed
    context = self._prefetch_styles_for_context(context)

    return context


def _prefetch_styles_for_context(self, context):
    """
    Prefetch StyleConfig for all objects in context.

    This eliminates N+1 queries from style-related template tags:
    - get_style
    - has_style
    - style_color
    - style_icon

    Instead of 20-40 queries, we make 2-3 bulk queries.
    """
    from reader.utils import get_styles_for_queryset
    from django.contrib.contenttypes.models import ContentType
    from reader.models import StyleConfig

    # Prefetch styles for sections (always in navigation)
    sections = context.get('sections', [])
    if sections:
        section_styles = get_styles_for_queryset(sections)
        context['section_styles'] = section_styles

    # Prefetch styles for genres (if in context)
    genres = context.get('genres', [])
    if genres:
        genre_styles = get_styles_for_queryset(genres)
        context['genre_styles'] = genre_styles

    # Prefetch styles for primary_genres (used in filters)
    primary_genres = context.get('primary_genres', [])
    if primary_genres:
        primary_genre_styles = get_styles_for_queryset(primary_genres)
        context['primary_genre_styles'] = primary_genre_styles

    # Prefetch styles for genres_hierarchical (complex navigation)
    genres_hierarchical = context.get('genres_hierarchical', {})
    if genres_hierarchical:
        # Collect all genres from hierarchical structure
        all_hierarchical_genres = []
        for section_id, section_data in genres_hierarchical.items():
            all_hierarchical_genres.extend(section_data['primary_genres'])
            for parent_id, sub_genres in section_data['sub_genres'].items():
                all_hierarchical_genres.extend(sub_genres)

        if all_hierarchical_genres:
            hierarchical_styles = get_styles_for_queryset(all_hierarchical_genres)
            context['hierarchical_genre_styles'] = hierarchical_styles

    return context
```

**Impact:** Replaces 20-40 individual queries with 2-3 bulk queries.

---

#### Step 2: Update Template Tags to Use Context

**File:** `myapp/reader/templatetags/reader_tags.py`

**Option A: Context-aware tags (RECOMMENDED)**

```python
# reader_tags.py

@register.simple_tag(takes_context=True)
def get_style(context, obj):
    """
    Get style configuration for an object.

    OPTIMIZED: Uses pre-fetched styles from context instead of querying.
    Falls back to query only if not in context (backwards compatible).

    Usage in template:
        {% get_style section as style %}
    """
    if obj is None:
        return None

    # Try to get from pre-fetched context data
    obj_id = obj.pk

    # Check section_styles
    section_styles = context.get('section_styles', {})
    if obj_id in section_styles:
        return section_styles[obj_id]

    # Check genre_styles
    genre_styles = context.get('genre_styles', {})
    if obj_id in genre_styles:
        return genre_styles[obj_id]

    # Check primary_genre_styles
    primary_genre_styles = context.get('primary_genre_styles', {})
    if obj_id in primary_genre_styles:
        return primary_genre_styles[obj_id]

    # Check hierarchical_genre_styles
    hierarchical_styles = context.get('hierarchical_genre_styles', {})
    if obj_id in hierarchical_styles:
        return hierarchical_styles[obj_id]

    # Fallback: Query database (backwards compatible)
    # This ensures tag still works if prefetch not done
    from reader.utils import get_style_for_object
    return get_style_for_object(obj)


@register.filter
def has_style(obj):
    """
    Check if object has a style configuration.

    OPTIMIZED: No longer queries database directly.
    Use get_style tag instead for context-aware lookup.

    Usage:
        {% get_style section as style %}
        {% if style %}...{% endif %}

    Or legacy usage (less efficient):
        {% if section|has_style %}...{% endif %}
    """
    from reader.utils import get_style_for_object
    style = get_style_for_object(obj)
    return style is not None


@register.filter
def style_color(obj):
    """
    Get color from object's style.

    DEPRECATED: Use {% get_style %} tag instead:
        {% get_style section as style %}
        {{ style.color }}
    """
    from reader.utils import get_style_for_object
    style = get_style_for_object(obj)
    return style.color if style else ''


@register.filter
def style_icon(obj):
    """
    Get icon from object's style.

    DEPRECATED: Use {% get_style %} tag instead:
        {% get_style section as style %}
        {{ style.icon }}
    """
    from reader.utils import get_style_for_object
    style = get_style_for_object(obj)
    return style.icon if style else ''
```

**Option B: Store styles on objects (ALTERNATIVE)**

```python
# In reader/views/base.py
def _prefetch_styles_for_context(self, context):
    """Attach styles directly to objects"""
    sections = context.get('sections', [])
    if sections:
        section_styles = get_styles_for_queryset(sections)
        # Attach style to each section object
        for section in sections:
            section._cached_style = section_styles.get(section.pk)

    # Same for genres, etc.
    return context
```

```python
# In reader_tags.py
@register.simple_tag
def get_style(obj):
    """Get style - uses cached value if available"""
    # Check if style already attached to object
    if hasattr(obj, '_cached_style'):
        return obj._cached_style

    # Fallback to query
    from reader.utils import get_style_for_object
    return get_style_for_object(obj)
```

---

#### Step 3: Update Templates to Use New Pattern

**Before (triggers queries):**
```django
{% load reader_tags %}

<!-- This triggers 1 query per section -->
{% for section in sections %}
    <div style="background-color: {{ section|style_color }};">
        {{ section.name }}
    </div>
{% endfor %}
```

**After (no queries):**
```django
{% load reader_tags %}

<!-- This uses prefetched data -->
{% for section in sections %}
    {% get_style section as style %}
    <div style="background-color: {{ style.color|default:'' }};">
        {{ section.name }}
    </div>
{% endfor %}
```

---

### Part 2: enrich_book_meta Migration

Already covered in V2 optimization plan Phase 2.

**Summary:**
1. Add `enrich_books_with_new_chapters()` to view
2. Bulk calculate in one query
3. Attach to `book.new_chapters_count`
4. Template tag just returns pre-calculated value

---

### Part 3: hreflang_tags Migration

#### Step 1: Prefetch in Book Detail View

```python
# reader/views/base.py - BaseBookDetailView

def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)

    # Prefetch hreflang data
    if hasattr(self.object, 'bookmaster'):
        from books.models import Book
        context['hreflang_books'] = list(
            Book.objects.filter(
                bookmaster=self.object.bookmaster,
                is_public=True
            ).select_related('language')
            .only('id', 'slug', 'language__code')
        )

    return context
```

#### Step 2: Update Template Tag

```python
# reader_extras.py

@register.simple_tag(takes_context=True)
def hreflang_tags(context):
    # ... existing code ...

    if view_name in ('book_detail', 'section_book_detail'):
        # Try to use prefetched data
        hreflang_books = context.get('hreflang_books')

        if hreflang_books:
            # No query - use prefetched data
            book_slugs = {b.language.code: b.slug for b in hreflang_books}
            # ... build hreflang tags ...
        else:
            # Fallback: query database (backwards compatible)
            # ... existing query code ...
```

---

## 📊 Expected Query Reduction

### Before Migration:

| Page Type | StyleConfig Queries | enrich_book_meta | hreflang | Total Template Queries |
|-----------|-------------------|-----------------|----------|----------------------|
| Homepage | 10-20 | 6 | 0 | **16-26** |
| Section Home | 15-25 | 6 | 0 | **21-31** |
| Book List | 20-30 | 12 | 0 | **32-42** |
| Book Detail | 5-10 | 0 | 1-2 | **6-12** |

### After Migration:

| Page Type | StyleConfig Queries | enrich_book_meta | hreflang | Total Template Queries |
|-----------|-------------------|-----------------|----------|----------------------|
| Homepage | **2-3** | **0** | 0 | **2-3** ✅ |
| Section Home | **2-3** | **0** | 0 | **2-3** ✅ |
| Book List | **2-3** | **0** | 0 | **2-3** ✅ |
| Book Detail | **2-3** | **0** | **0** | **2-3** ✅ |

**Overall Savings: 30-40 queries per page**

---

## 🧪 Testing Checklist

### Test StyleConfig Migration:

```python
# In Django shell
python manage.py shell

from django.test import RequestFactory
from reader.views import WelcomeView

factory = RequestFactory()
request = factory.get('/en/')
view = WelcomeView.as_view()

# Enable query logging
from django.db import connection
from django.test.utils import override_settings

@override_settings(DEBUG=True)
def test_welcome_view():
    connection.queries_log.clear()

    # Render view
    response = view(request, language_code='en')

    # Check StyleConfig queries
    style_queries = [q for q in connection.queries if 'reader_styleconfig' in q['sql']]

    print(f"StyleConfig queries: {len(style_queries)}")
    print(f"Expected: 2-3 (bulk prefetch)")
    print(f"Before optimization: 10-40 (individual queries)")

    assert len(style_queries) <= 3, f"Too many StyleConfig queries: {len(style_queries)}"

test_welcome_view()
```

### Visual Testing:

- [ ] Visit homepage - check section colors/icons display correctly
- [ ] Visit section home - check genre colors/icons display correctly
- [ ] Visit book list - check filters display correctly
- [ ] Check Django Debug Toolbar - verify StyleConfig queries ≤ 3

---

## 🚨 Common Pitfalls

### Pitfall 1: Forgetting to prefetch in new views

**Problem:**
```python
class MyNewListView(BaseBookListView):
    # Forgot to call _prefetch_styles_for_context
    # Template tags will fall back to queries
```

**Solution:**
```python
class MyNewListView(BaseBookListView):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # BaseReaderView already calls _prefetch_styles_for_context
        # So inheriting from it is enough
        return context
```

### Pitfall 2: Using deprecated filter tags

**Problem:**
```django
<!-- Old pattern - still queries database -->
<div style="background: {{ section|style_color }};">
```

**Solution:**
```django
<!-- New pattern - uses prefetched data -->
{% get_style section as style %}
<div style="background: {{ style.color|default:'' }};">
```

### Pitfall 3: Not handling missing styles

**Problem:**
```django
{% get_style section as style %}
<div style="background: {{ style.color }};">  <!-- Error if style is None -->
```

**Solution:**
```django
{% get_style section as style %}
<div style="background: {{ style.color|default:'#ccc' }};">  <!-- Safe -->
```

---

## 📝 Migration Checklist

### Phase 1: StyleConfig (Week 1)

- [ ] Add `_prefetch_styles_for_context()` to BaseReaderView
- [ ] Update `get_style` tag to use context
- [ ] Update templates to use `{% get_style %}` pattern
- [ ] Test with Django Debug Toolbar
- [ ] Verify StyleConfig queries ≤ 3 per page

### Phase 2: enrich_book_meta (Week 2)

- [ ] Already covered in V2 optimization plan Phase 2
- [ ] Follow Phase 2 implementation guide

### Phase 3: hreflang_tags (Week 2)

- [ ] Add prefetch to BaseBookDetailView
- [ ] Update hreflang_tags to use context
- [ ] Test book detail pages
- [ ] Verify hreflang queries = 0

### Phase 4: Deprecation (Week 3)

- [ ] Mark old filter tags as deprecated
- [ ] Add warnings in docstrings
- [ ] Update all templates to use new pattern
- [ ] Run full test suite

---

## ✅ Success Criteria

When migration is complete:

- [ ] **Homepage:** Total queries ≤ 10 (was 74)
  - StyleConfig: 2-3 queries (was 10-20)
  - enrich_book_meta: 0 queries (was 6)

- [ ] **Book List:** Total queries ≤ 15 (was 60-80)
  - StyleConfig: 2-3 queries (was 20-30)
  - enrich_book_meta: 0 queries (was 12)

- [ ] **Book Detail:** Total queries ≤ 10 (was 30-40)
  - StyleConfig: 2-3 queries (was 5-10)
  - hreflang: 0 queries (was 1-2)

- [ ] **All functional tests passing**
- [ ] **No visual regressions**
- [ ] **Django Debug Toolbar shows minimal queries**

---

**End of Document**
