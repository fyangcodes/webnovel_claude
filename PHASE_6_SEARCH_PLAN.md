# Phase 6: Search Implementation - Detailed Plan

## Overview
Implement fast, multi-language keyword search using the BookKeyword denormalized index. This phase builds on the existing taxonomy infrastructure to provide weighted, relevance-ranked search results.

**Total Estimated Time**: 8-12 hours
**Dependencies**: Phase 1-5 complete (BookKeyword model exists, signals populate keywords)

---

## 📊 Architecture Overview

### Search Flow
```
User Query → BookSearchService → BookKeyword Index → Weighted Results → Book Queryset → Template
```

### Key Components
1. **BookKeyword Model** (Already exists): Denormalized search index
2. **BookSearchService** (New): Search logic and ranking
3. **BookSearchView** (New): Search interface view
4. **search.html** (New): Search results template

---

## 🎯 Task Breakdown

### **TASK 1: Create BookSearchService** (3-4 hours)

**File**: `/myapp/books/utils/search.py` (New file)

#### 1.1 Service Class Structure
```python
class BookSearchService:
    """
    Multi-language keyword search service using BookKeyword index.

    Features:
    - Keyword-based search across sections, genres, tags, entities
    - Multi-language support
    - Weighted relevance ranking
    - Filter by section, genre, tag, status
    - Pagination support
    """

    @staticmethod
    def search(
        query: str,
        language_code: str,
        section_slug: str = None,
        genre_slug: str = None,
        tag_slug: str = None,
        status: str = None,
        limit: int = 50
    ) -> Dict[str, Any]:
        """
        Search for books by keyword with optional filters.

        Args:
            query: Search query string
            language_code: Target language for search
            section_slug: Optional section filter
            genre_slug: Optional genre filter
            tag_slug: Optional tag filter
            status: Optional book status filter (ongoing/completed)
            limit: Maximum results to return

        Returns:
            {
                'books': List of Book objects,
                'total_results': Total count,
                'matched_keywords': List of matched keywords,
                'search_time_ms': Search duration in milliseconds
            }
        """
```

#### 1.2 Implementation Steps

**Step 1: Query Parsing and Normalization**
```python
def _normalize_query(query: str) -> List[str]:
    """
    Normalize and tokenize search query.

    - Strip whitespace
    - Convert to lowercase
    - Split on whitespace
    - Remove empty tokens
    - Return list of keywords
    """
```

**Step 2: Keyword Matching**
```python
def _find_matching_keywords(tokens: List[str], language_code: str) -> QuerySet:
    """
    Find BookKeyword records matching query tokens.

    Strategy:
    1. Exact matches (highest weight)
    2. Prefix matches (medium weight)
    3. Contains matches (lowest weight)

    Returns BookKeyword queryset with annotations for match type.
    """
```

**Step 3: BookMaster Aggregation and Scoring**
```python
def _aggregate_bookmaster_scores(keywords_qs: QuerySet) -> Dict[int, float]:
    """
    Aggregate keyword matches per bookmaster with weighted scoring.

    Score calculation:
    - Sum(keyword.weight * match_type_multiplier)
    - match_type_multiplier: exact=3.0, prefix=2.0, contains=1.0

    Returns: {bookmaster_id: total_score}
    """
```

**Step 4: Apply Filters**
```python
def _apply_filters(
    bookmaster_ids: List[int],
    language_code: str,
    section_slug: str = None,
    genre_slug: str = None,
    tag_slug: str = None,
    status: str = None
) -> QuerySet:
    """
    Filter books by section, genre, tag, and status.

    Returns Book queryset filtered by all criteria.
    """
```

**Step 5: Rank and Return Results**
```python
def _rank_results(books_qs: QuerySet, scores: Dict[int, float]) -> List[Book]:
    """
    Sort books by relevance score and enrich with metadata.

    - Annotate each book with search_score
    - Order by score DESC
    - Prefetch related data for templates
    """
```

#### 1.3 Full Method Example
```python
@staticmethod
def search(query, language_code, section_slug=None, genre_slug=None,
           tag_slug=None, status=None, limit=50):
    import time
    start_time = time.time()

    # 1. Normalize query
    tokens = BookSearchService._normalize_query(query)
    if not tokens:
        return {
            'books': [],
            'total_results': 0,
            'matched_keywords': [],
            'search_time_ms': 0
        }

    # 2. Find matching keywords
    keywords_qs = BookSearchService._find_matching_keywords(tokens, language_code)

    # 3. Aggregate scores per bookmaster
    scores = BookSearchService._aggregate_bookmaster_scores(keywords_qs)

    if not scores:
        return {
            'books': [],
            'total_results': 0,
            'matched_keywords': [],
            'search_time_ms': (time.time() - start_time) * 1000
        }

    # 4. Get Book queryset with filters
    bookmaster_ids = list(scores.keys())
    books_qs = BookSearchService._apply_filters(
        bookmaster_ids, language_code, section_slug,
        genre_slug, tag_slug, status
    )

    # 5. Rank and limit results
    books = BookSearchService._rank_results(books_qs, scores)[:limit]

    # Get matched keywords for display
    matched_keywords = list(
        keywords_qs.values_list('keyword', flat=True).distinct()[:10]
    )

    search_time = (time.time() - start_time) * 1000

    return {
        'books': books,
        'total_results': len(books),
        'matched_keywords': matched_keywords,
        'search_time_ms': round(search_time, 2)
    }
```

#### 1.4 Helper Methods
```python
@staticmethod
def suggest_keywords(prefix: str, language_code: str, limit: int = 10) -> List[str]:
    """
    Auto-suggest keywords for search box.

    Returns list of keywords starting with prefix.
    """

@staticmethod
def get_popular_searches(language_code: str, limit: int = 10) -> List[Dict]:
    """
    Get most common search keywords (could be based on SearchLog).

    Returns list of {keyword, count} dicts.
    """
```

---

### **TASK 2: Create BookSearchView** (2-3 hours)

**File**: `/myapp/reader/views.py` (Add to existing file)

#### 2.1 View Implementation
```python
class BookSearchView(BaseBookListView):
    """
    Search view with keyword search and filtering.

    URL: /<language_code>/search/?q=<query>&section=<slug>&genre=<slug>...
    """

    template_name = "reader/search.html"
    paginate_by = 20

    def get_queryset(self):
        """
        Use BookSearchService to get search results.
        """
        query = self.request.GET.get('q', '').strip()

        if not query:
            # Return empty queryset if no query
            return Book.objects.none()

        language_code = self.kwargs.get('language_code')

        # Get filter parameters
        section_slug = self.request.GET.get('section')
        genre_slug = self.request.GET.get('genre')
        tag_slug = self.request.GET.get('tag')
        status = self.request.GET.get('status')

        # Perform search
        from books.utils.search import BookSearchService
        results = BookSearchService.search(
            query=query,
            language_code=language_code,
            section_slug=section_slug,
            genre_slug=genre_slug,
            tag_slug=tag_slug,
            status=status,
            limit=100  # Get more for pagination
        )

        # Store results in instance for get_context_data
        self.search_results = results

        # Return Book queryset (already filtered and ranked)
        return results['books']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Add search metadata
        context['search_query'] = self.request.GET.get('q', '')
        context['search_results'] = getattr(self, 'search_results', {})
        context['matched_keywords'] = context['search_results'].get('matched_keywords', [])
        context['search_time_ms'] = context['search_results'].get('search_time_ms', 0)

        # Add filter values
        context['selected_section'] = self.request.GET.get('section', '')
        context['selected_genre'] = self.request.GET.get('genre', '')
        context['selected_tag'] = self.request.GET.get('tag', '')
        context['selected_status'] = self.request.GET.get('status', '')

        return context
```

#### 2.2 URL Pattern
**File**: `/myapp/reader/urls.py`

Add to urlpatterns:
```python
# Search page
path(
    "<str:language_code>/search/",
    views.BookSearchView.as_view(),
    name="search",
),
```

---

### **TASK 3: Create Search Template** (2-3 hours)

**File**: `/myapp/reader/templates/reader/search.html` (New file)

#### 3.1 Template Structure
```django
{% extends "reader/base.html" %}
{% load books_extras %}
{% load reader_extras %}
{% load static %}

{% block title %}Search Results{% endblock %}

{% block breadcrumb_check %}
<nav aria-label="breadcrumb" class="d-none d-md-block ms-2">
    <ol class="breadcrumb mb-0">
        <li class="breadcrumb-item">
            <a href="{% url 'reader:book_list' current_language.code %}">All Books</a>
        </li>
        <li class="breadcrumb-item active" aria-current="page">
            Search: "{{ search_query }}"
        </li>
    </ol>
</nav>
{% endblock %}

{% block content %}
<!-- Search Box -->
<section class="mt-3 mb-4">
    <form method="get" action="{% url 'reader:search' current_language.code %}">
        <div class="input-group input-group-lg">
            <input type="text"
                   name="q"
                   class="form-control"
                   placeholder="Search books by title, genre, tags..."
                   value="{{ search_query }}"
                   autofocus>
            <button class="btn btn-primary-custom" type="submit">
                <i class="fas fa-search"></i> Search
            </button>
        </div>

        <!-- Preserve filters -->
        {% if selected_section %}
        <input type="hidden" name="section" value="{{ selected_section }}">
        {% endif %}
        {% if selected_genre %}
        <input type="hidden" name="genre" value="{{ selected_genre }}">
        {% endif %}
        {% if selected_tag %}
        <input type="hidden" name="tag" value="{{ selected_tag }}">
        {% endif %}
        {% if selected_status %}
        <input type="hidden" name="status" value="{{ selected_status }}">
        {% endif %}
    </form>
</section>

<!-- Search Metadata -->
{% if search_query %}
<section class="mb-3">
    <div class="d-flex justify-content-between align-items-center">
        <div>
            <h5 class="mb-0">
                Found <strong>{{ paginator.count }}</strong> result{{ paginator.count|pluralize }}
                {% if matched_keywords %}
                <small class="text-muted">
                    (matched: {{ matched_keywords|join:", " }})
                </small>
                {% endif %}
            </h5>
        </div>
        <small class="text-muted">Search time: {{ search_time_ms }}ms</small>
    </div>
</section>
{% endif %}

<!-- Filters (same as book_list.html) -->
<section class="mb-4">
    <div class="card">
        <div class="card-body">
            <!-- Section Filter -->
            {% if sections %}
            <div class="mb-3">
                <h6 class="text-muted mb-2">Section</h6>
                <div class="d-flex flex-wrap gap-2">
                    <a href="?{% query_transform request section=None page=None %}"
                       class="btn btn-sm btn-min-width {% if not request.GET.section %}btn-primary-custom{% else %}btn-outline-primary-custom{% endif %}">
                        All Sections
                    </a>
                    {% for section in sections %}
                        <a href="?{% query_transform request section=section.slug page=None %}"
                           class="btn btn-sm btn-min-width {% if request.GET.section == section.slug %}btn-primary-custom{% else %}btn-outline-primary-custom{% endif %}">
                            {{ section.localized_name }}
                        </a>
                    {% endfor %}
                </div>
            </div>
            {% endif %}

            <!-- Similar for Genre, Tag, Status filters -->
            <!-- ... (same as book_list.html) ... -->
        </div>
    </div>
</section>

<!-- Search Results -->
<section>
    {% if books %}
        <div class="book-grid">
            {% for book in books %}
                {% include "reader/partials/book_card.html" with book=book current_language=current_language %}
            {% endfor %}
        </div>

        <!-- Pagination -->
        {% if is_paginated %}
        <nav aria-label="Search results pagination" class="mt-4">
            <!-- Standard Django pagination -->
        </nav>
        {% endif %}
    {% elif search_query %}
        <!-- No Results State -->
        <div class="text-center py-5">
            <div class="display-1 mb-3">🔍</div>
            <h3>No books found</h3>
            <p class="text-muted">
                Try different keywords or adjust your filters.
            </p>
            <a href="{% url 'reader:book_list' current_language.code %}"
               class="btn btn-outline-primary-custom">
                Browse All Books
            </a>
        </div>
    {% else %}
        <!-- Empty Search State -->
        <div class="text-center py-5">
            <div class="display-1 mb-3">🔍</div>
            <h3>Search for books</h3>
            <p class="text-muted">
                Enter keywords to search across titles, genres, and tags.
            </p>
        </div>
    {% endif %}
</section>
{% endblock %}
```

---

### **TASK 4: Add Search to Navigation** (1 hour)

**File**: `/myapp/reader/templates/reader/base.html`

#### 4.1 Add Search Button to Navbar
```django
<!-- In navbar, after logo/breadcrumb, before settings dropdown -->
<div class="flex-grow-1 mx-3 d-none d-md-block">
    <form method="get" action="{% url 'reader:search' current_language.code %}" class="d-flex">
        <div class="input-group input-group-sm">
            <input type="text"
                   name="q"
                   class="form-control"
                   placeholder="Search..."
                   value="{{ request.GET.q }}">
            <button class="btn btn-outline-secondary" type="submit">
                <i class="fas fa-search"></i>
            </button>
        </div>
    </form>
</div>
```

#### 4.2 Add Mobile Search Button
```django
<!-- Mobile search icon that opens search page -->
<a href="{% url 'reader:search' current_language.code %}"
   class="btn btn-nav d-md-none">
    <i class="fas fa-search"></i>
</a>
```

---

### **TASK 5: Add Search Autocomplete (Optional Enhancement)** (2 hours)

**File**: `/myapp/reader/views.py`

#### 5.1 Create Autocomplete API Endpoint
```python
from django.http import JsonResponse

def search_autocomplete(request):
    """
    API endpoint for search autocomplete suggestions.

    GET /api/search/autocomplete/?q=<prefix>&lang=<code>

    Returns: {
        "suggestions": [
            {"text": "Romance", "type": "genre", "count": 15},
            {"text": "BL", "type": "section", "count": 8},
            ...
        ]
    }
    """
    prefix = request.GET.get('q', '').strip()
    language_code = request.GET.get('lang', 'en')

    if len(prefix) < 2:
        return JsonResponse({'suggestions': []})

    from books.utils.search import BookSearchService
    keywords = BookSearchService.suggest_keywords(prefix, language_code, limit=10)

    return JsonResponse({
        'suggestions': keywords
    })
```

#### 5.2 Add URL Pattern
```python
# API endpoint for autocomplete
path(
    "api/search/autocomplete/",
    views.search_autocomplete,
    name="search_autocomplete",
),
```

#### 5.3 Add JavaScript to Search Template
```javascript
<script>
// Simple autocomplete using datalist
const searchInput = document.querySelector('input[name="q"]');
const datalist = document.createElement('datalist');
datalist.id = 'search-suggestions';
searchInput.setAttribute('list', 'search-suggestions');
searchInput.parentNode.appendChild(datalist);

let debounceTimeout;
searchInput.addEventListener('input', function(e) {
    clearTimeout(debounceTimeout);
    const query = e.target.value;

    if (query.length < 2) {
        datalist.innerHTML = '';
        return;
    }

    debounceTimeout = setTimeout(() => {
        fetch(`/api/search/autocomplete/?q=${encodeURIComponent(query)}&lang={{ current_language.code }}`)
            .then(res => res.json())
            .then(data => {
                datalist.innerHTML = data.suggestions
                    .map(s => `<option value="${s.text}">${s.type}: ${s.count} books</option>`)
                    .join('');
            });
    }, 300);
});
</script>
```

---

## 🔄 Implementation Order (Critical Path)

1. **TASK 1** (BookSearchService) - Core search logic
2. **TASK 2** (BookSearchView) - Search endpoint
3. **TASK 3** (Search Template) - User interface
4. **TASK 4** (Navigation Integration) - Make search accessible
5. **TASK 5** (Autocomplete) - Optional enhancement

**Minimum Viable Search**: Tasks 1-3 (7-10 hours)
**Full Featured Search**: All tasks (8-12 hours)

---

## ✅ Testing Checklist

### Unit Tests (BookSearchService)
- [ ] Empty query returns no results
- [ ] Exact keyword match returns correct books
- [ ] Prefix match works (e.g., "Rom" finds "Romance")
- [ ] Multi-word query works ("BL Romance")
- [ ] Language filtering works (only searches in target language)
- [ ] Section filter narrows results correctly
- [ ] Genre filter narrows results correctly
- [ ] Tag filter narrows results correctly
- [ ] Status filter works (ongoing/completed)
- [ ] Weighted ranking: exact > prefix > contains
- [ ] Performance: Large keyword set < 100ms

### Integration Tests (BookSearchView)
- [ ] Search page loads without errors
- [ ] Query parameter `q` is respected
- [ ] Empty query shows empty state
- [ ] Results display with book cards
- [ ] Pagination works for > 20 results
- [ ] Filters preserve search query
- [ ] Search query preserves filters
- [ ] Breadcrumb shows search query
- [ ] Matched keywords displayed

### UI/UX Tests
- [ ] Search box in navbar works
- [ ] Mobile search button redirects correctly
- [ ] Search results are relevant
- [ ] "No results" state is clear
- [ ] Search time displayed
- [ ] Filter buttons work with search
- [ ] Book cards show correct info

### Performance Tests
- [ ] Search with 1000+ keywords < 200ms
- [ ] BookKeyword indexes are used (EXPLAIN)
- [ ] No N+1 queries in results page
- [ ] Prefetching works for book cards

---

## 🛡️ Safety & Rollback

### Backward Compatibility
- No changes to existing views or templates
- New URL patterns don't conflict
- BookKeyword model already exists
- All changes are additive

### Rollback Procedure
1. Remove search URL pattern from `urls.py`
2. Delete `search.html` template
3. Remove search form from `base.html`
4. Delete `books/utils/search.py`
5. Remove BookSearchView from `views.py`

No database changes required - BookKeyword model remains unchanged.

---

## 📝 Files Created/Modified

### New Files
- `/myapp/books/utils/search.py` (~200 lines)
- `/myapp/reader/templates/reader/search.html` (~150 lines)

### Modified Files
- `/myapp/reader/views.py` (Add BookSearchView, ~60 lines)
- `/myapp/reader/urls.py` (Add 1-2 URL patterns, ~5 lines)
- `/myapp/reader/templates/reader/base.html` (Add search box, ~15 lines)

**Total New Code**: ~430 lines
**Complexity**: Medium

---

## 🎯 Success Metrics

After implementation, users should be able to:
1. Search for books by any keyword (section, genre, tag, entity)
2. Get results in < 200ms for typical queries
3. Filter search results by section, genre, tag, status
4. See which keywords matched their query
5. Navigate from search to book detail seamlessly

---

## 📚 Example Searches

### Expected Behavior
- Query: `"BL"` → Returns all BL section books
- Query: `"Romance"` → Returns books with Romance genre
- Query: `"Slow Burn"` → Returns books with slow-burn tag
- Query: `"BL Romance"` → Returns BL books with Romance genre
- Query: `"魏无羡"` (Wei Wuxian) → Returns books with this entity/character

### Edge Cases
- Empty query → Show empty state
- No results → Show "no results" message
- Very long query → Truncate/normalize
- Special characters → Handle gracefully
- Non-existent language → Fallback to 'en'

---

## Next Steps After Phase 6

After search implementation, consider:
- **Phase 7**: Add model validation and constraints
- **Phase 8**: Write comprehensive tests and documentation
- **Search Analytics**: Track popular searches
- **Advanced Search**: Boolean operators (AND, OR, NOT)
- **Search History**: Save user's recent searches
- **Faceted Search**: Show filter counts in sidebar
