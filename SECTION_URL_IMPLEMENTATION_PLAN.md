# Section-Based URL Routing Implementation Plan

**Project:** Webnovel Translation Platform
**Date:** 2025-11-16
**Objective:** Implement section-scoped URL routing for better SEO and user experience

---

## Table of Contents

1. [Current State Analysis](#current-state-analysis)
2. [New URL Structure Design](#new-url-structure-design)
3. [Implementation Steps](#implementation-steps)
4. [File Changes Summary](#file-changes-summary)
5. [Testing Plan](#testing-plan)
6. [Rollout Strategy](#rollout-strategy)
7. [Estimated Effort](#estimated-effort)
8. [Decision Points](#decision-points)

---

## Current State Analysis

### Current URL Structure

```
/                                    → language_redirect
/<language_code>/                    → WelcomeView (all sections)
/<language_code>/books/              → BookListView (section via ?section=slug)
/<language_code>/genre/<genre_slug>/ → GenreBookListView (redirects to books with ?genre=slug)
/<language_code>/tag/<tag_slug>/     → TagBookListView (redirects to books with ?tag=slug)
/<language_code>/search/             → BookSearchView
/<language_code>/book/<book_slug>/   → BookDetailView
/<language_code>/book/<book_slug>/<chapter_slug>/ → ChapterDetailView
```

### Current Issues

- ❌ Sections are only accessible via query parameters (`?section=fiction`)
- ❌ No dedicated section landing pages
- ❌ URLs don't reflect content hierarchy
- ❌ Difficult to bookmark specific sections
- ❌ Poor SEO - search engines can't easily index section-specific content
- ❌ Not intuitive for users

### Current Implementation

**Files Involved:**
- `myapp/reader/urls.py` - URL patterns
- `myapp/reader/views.py` - View classes (BaseBookListView, BookListView, etc.)
- `myapp/reader/templates/reader/*.html` - Templates
- `myapp/reader/cache/static_data.py` - Caching functions

**Current Features:**
- Section filtering via GET parameters
- Hierarchical genre structure grouped by section
- Cached sections with localized names
- Section badges on book cards

---

## New URL Structure Design

### Proposed URL Patterns

#### Homepage & Global Views

```
/                                    → language_redirect
/<language_code>/                    → WelcomeView (all sections)
/<language_code>/browse/             → BookListView (all sections - OPTIONAL)
/<language_code>/search/             → BookSearchView (global search)
```

#### Section-Scoped Views (MAIN PATTERN)

```
/<language_code>/<section_slug>/                              → SectionHomeView
/<language_code>/<section_slug>/books/                        → SectionBookListView
/<language_code>/<section_slug>/genre/<genre_slug>/           → SectionGenreBookListView
/<language_code>/<section_slug>/tag/<tag_slug>/               → SectionTagBookListView
/<language_code>/<section_slug>/search/                       → SectionSearchView
/<language_code>/<section_slug>/book/<book_slug>/             → SectionBookDetailView
/<language_code>/<section_slug>/book/<book_slug>/<chapter_slug>/ → SectionChapterDetailView
```

### URL Examples

| URL | Description |
|-----|-------------|
| `/zh/fiction/` | Fiction section home in Chinese |
| `/zh/fiction/books/` | All fiction books in Chinese |
| `/zh/fiction/genre/cultivation/` | Cultivation novels in Chinese fiction |
| `/zh/fiction/genre/cultivation/?status=ongoing` | Ongoing cultivation novels |
| `/zh/bl/` | BL section home in Chinese |
| `/zh/bl/book/my-novel/` | BL novel detail page |
| `/en/gl/book/her-story/chapter-1/` | GL chapter in English |
| `/zh/fiction/search/?q=cultivation` | Search within fiction section |
| `/zh/search/?q=romance` | Global search across all sections |

### Benefits

✅ **SEO-friendly:** Clear hierarchy in URLs
✅ **User-friendly:** Easy to understand and share
✅ **Bookmarkable:** Direct links to specific sections
✅ **Organized:** Content grouped by section
✅ **Scalable:** Easy to add new sections
✅ **Semantic:** URLs reflect content structure

---

## Implementation Steps

### Phase 1: Backend - URL & View Updates

#### 1.1 Update URL Patterns

**File:** `myapp/reader/urls.py`

**Tasks:**
- [ ] Add new section-scoped URL patterns
- [ ] Keep old patterns for backward compatibility (temporary)
- [ ] Add URL names with `section_` prefix
- [ ] Register slug converter (already exists: `UnicodeSlugConverter`)

**New URL Patterns:**

```python
# Section-scoped views
path(
    "<str:language_code>/<slug:section_slug>/",
    views.SectionHomeView.as_view(),
    name="section_home",
),
path(
    "<str:language_code>/<slug:section_slug>/books/",
    views.SectionBookListView.as_view(),
    name="section_book_list",
),
path(
    "<str:language_code>/<slug:section_slug>/genre/<slug:genre_slug>/",
    views.SectionGenreBookListView.as_view(),
    name="section_genre_book_list",
),
path(
    "<str:language_code>/<slug:section_slug>/tag/<slug:tag_slug>/",
    views.SectionTagBookListView.as_view(),
    name="section_tag_book_list",
),
path(
    "<str:language_code>/<slug:section_slug>/search/",
    views.SectionSearchView.as_view(),
    name="section_search",
),
path(
    "<str:language_code>/<slug:section_slug>/book/<uslug:book_slug>/",
    views.SectionBookDetailView.as_view(),
    name="section_book_detail",
),
path(
    "<str:language_code>/<slug:section_slug>/book/<uslug:book_slug>/<uslug:chapter_slug>/",
    views.SectionChapterDetailView.as_view(),
    name="section_chapter_detail",
),
```

**Backward Compatibility Redirects:**

```python
# Redirect old patterns to new section-based patterns
path(
    "<str:language_code>/books/",
    views.LegacyBookListRedirectView.as_view(),
    name="legacy_book_list",
),
path(
    "<str:language_code>/book/<uslug:book_slug>/",
    views.LegacyBookDetailRedirectView.as_view(),
    name="legacy_book_detail",
),
# ... other legacy redirects
```

---

#### 1.2 Create SectionMixin

**File:** `myapp/reader/mixins.py` (NEW)

**Purpose:**
- Validate section from URL kwargs
- Add section to context
- Handle 404 for invalid sections
- Permission checks (staff-only sections if needed)

**Implementation:**

```python
from django.shortcuts import get_object_or_404
from django.http import Http404
from books.models import Section

class SectionMixin:
    """
    Mixin for views that require a section from the URL.

    Validates section exists and adds it to context.
    """

    def get_section(self):
        """
        Get section from URL kwargs and validate.

        Returns:
            Section object

        Raises:
            Http404: If section doesn't exist
        """
        section_slug = self.kwargs.get("section_slug")
        section = get_object_or_404(Section, slug=section_slug)

        # TODO: Add permission checks if needed
        # e.g., if section.is_mature and not user.is_authenticated:
        #     raise PermissionDenied("Must be logged in to view mature content")

        return section

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["current_section"] = self.get_section()
        return context
```

**Tasks:**
- [ ] Create `myapp/reader/mixins.py`
- [ ] Implement `SectionMixin` class
- [ ] Add section validation logic
- [ ] Add permission checks (if needed for mature content)

---

#### 1.3 Update View Classes

**File:** `myapp/reader/views.py`

**New View Classes:**

1. **SectionHomeView** - Section landing page
2. **SectionBookListView** - Books filtered by section
3. **SectionGenreBookListView** - Redirect to SectionBookListView with genre filter
4. **SectionTagBookListView** - Redirect to SectionBookListView with tag filter
5. **SectionSearchView** - Search within section
6. **SectionBookDetailView** - Book detail with section context
7. **SectionChapterDetailView** - Chapter reading with section context

**Implementation Structure:**

```python
from reader.mixins import SectionMixin

class SectionHomeView(SectionMixin, TemplateView):
    """Section landing page with featured content"""
    template_name = "reader/section_home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        section = self.get_section()
        language_code = self.kwargs.get("language_code")

        # Featured books from this section
        # Recent updates in this section
        # Top genres in this section

        return context

class SectionBookListView(SectionMixin, BaseBookListView):
    """Books filtered by section"""
    template_name = "reader/book_list.html"

    def get_queryset(self):
        language = self.get_language()
        section = self.get_section()

        queryset = Book.objects.filter(
            language=language,
            is_public=True,
            bookmaster__section=section
        )

        # Apply additional filters (genre, tag, status)
        # ... existing filter logic ...

        return queryset

# ... similar implementations for other views
```

**Tasks:**
- [ ] Create `SectionHomeView`
- [ ] Create `SectionBookListView` (inherits from `SectionMixin` + `BaseBookListView`)
- [ ] Create `SectionGenreBookListView` (redirect view)
- [ ] Create `SectionTagBookListView` (redirect view)
- [ ] Create `SectionSearchView` (inherits from `SectionMixin` + `BookSearchView`)
- [ ] Create `SectionBookDetailView` (inherits from `SectionMixin` + `DetailView`)
- [ ] Create `SectionChapterDetailView` (inherits from `SectionMixin` + `DetailView`)
- [ ] Update querysets to filter by section
- [ ] Update context data methods

---

#### 1.4 Add Redirect Views

**File:** `myapp/reader/views.py`

**Purpose:** Redirect old query-based URLs to new path-based URLs

**Implementation:**

```python
class LegacyBookListRedirectView(RedirectView):
    """
    Redirect old book list URLs to new section-based URLs.

    Example:
    /zh/books/?section=fiction → /zh/fiction/books/
    /zh/books/ → /zh/browse/ (or show all sections)
    """
    permanent = False  # Use 302 (temporary) during migration

    def get_redirect_url(self, *args, **kwargs):
        language_code = kwargs.get("language_code")
        section_slug = self.request.GET.get("section")

        if section_slug:
            # Redirect to section-specific book list
            url = reverse("reader:section_book_list", args=[language_code, section_slug])

            # Preserve other query params (genre, tag, status, page)
            query_params = self.request.GET.copy()
            query_params.pop("section", None)

            if query_params:
                url += f"?{query_params.urlencode()}"

            return url
        else:
            # No section specified - redirect to browse all
            return reverse("reader:browse", args=[language_code])

class LegacyBookDetailRedirectView(RedirectView):
    """
    Redirect old book detail URLs to new section-based URLs.

    Example:
    /zh/book/my-novel/ → /zh/fiction/book/my-novel/
    """
    permanent = False

    def get_redirect_url(self, *args, **kwargs):
        language_code = kwargs.get("language_code")
        book_slug = kwargs.get("book_slug")

        # Look up book and get its section
        book = get_object_or_404(
            Book,
            slug=book_slug,
            language__code=language_code,
            is_public=True
        )

        section_slug = book.bookmaster.section.slug

        return reverse(
            "reader:section_book_detail",
            args=[language_code, section_slug, book_slug]
        )

# Similar redirects for chapter detail, genre, tag views
```

**Tasks:**
- [ ] Create `LegacyBookListRedirectView`
- [ ] Create `LegacyBookDetailRedirectView`
- [ ] Create `LegacyChapterDetailRedirectView`
- [ ] Create `LegacyGenreBookListRedirectView`
- [ ] Create `LegacyTagBookListRedirectView`
- [ ] Handle query parameter preservation
- [ ] Add error handling for books without sections

---

### Phase 2: Frontend - Template Updates

#### 2.1 Update Base Template

**File:** `myapp/reader/templates/reader/base.html`

**Changes:**

1. **Search Form (Line 58):** Make section-aware

```html
<!-- Search Box (Desktop) -->
{% if current_language %}
<div class="flex-grow-1 mx-3 d-none d-md-block" style="max-width: 400px;">
    <form method="get" action="{% if current_section %}{% url 'reader:section_search' current_language.code current_section.slug %}{% else %}{% url 'reader:search' current_language.code %}{% endif %}" class="d-flex">
        <input type="text"
               name="q"
               class="form-control form-control-sm"
               placeholder="Search{% if current_section %} in {{ current_section.localized_name }}{% endif %}..."
               value="{% if request.resolver_match.url_name == 'search' or request.resolver_match.url_name == 'section_search' %}{{ request.GET.q }}{% endif %}">
        <button class="btn btn-sm btn-outline-secondary ms-1" type="submit">
            <i class="fas fa-search"></i>
        </button>
    </form>
</div>
{% endif %}
```

2. **Section Navigation Bar (Line 108-128):** Update links to use section-scoped URLs

```html
<!-- Section Navigation Bar -->
{% if sections and current_language %}
<div class="section-nav py-2 border-bottom">
    <div class="container">
        <div class="d-flex gap-2 flex-wrap align-items-center">
            <!-- All Sections Link -->
            <a href="{% url 'reader:welcome' current_language.code %}"
               class="btn btn-sm {% if not current_section %}btn-primary-custom{% else %}btn-outline-primary-custom{% endif %}">
                All
            </a>

            <!-- Section Links -->
            {% for section in sections %}
            <a href="{% url 'reader:section_home' current_language.code section.slug %}"
               class="btn btn-sm {% if current_section and current_section.slug == section.slug %}btn-primary-custom{% else %}btn-outline-primary-custom{% endif %}">
                {{ section.localized_name }}
            </a>
            {% endfor %}
        </div>
    </div>
</div>
{% endif %}
```

3. **Offcanvas Genre Menu (Line 132-196):** Update genre links to be section-aware

```html
<!-- Primary Genre -->
<a class="btn btn-outline-primary-custom btn-sm w-100 text-start"
   href="{% if current_section and genre.section.slug == current_section.slug %}{% url 'reader:section_genre_book_list' current_language.code current_section.slug genre.slug %}{% else %}{% url 'reader:section_genre_book_list' current_language.code genre.section.slug genre.slug %}{% endif %}">
    {{ genre.localized_name }}
</a>
```

**Tasks:**
- [ ] Update search form to be section-aware
- [ ] Update section navigation bar links
- [ ] Update offcanvas genre menu links
- [ ] Update "All Books" link to use new URL

---

#### 2.2 Update Book List Template

**File:** `myapp/reader/templates/reader/book_list.html`

**Changes:**

1. **Breadcrumbs (Line 8-42):** Update to show section hierarchy

```html
{% block breadcrumb_check %}
    <!-- Breadcrumb Navigation -->
    {% if current_section or current_genre or current_tag %}
    <nav aria-label="breadcrumb" class="d-none d-md-block ms-2">
        <ol class="breadcrumb mb-0">
            <li class="breadcrumb-item">
                <a href="{% url 'reader:welcome' current_language.code %}">Home</a>
            </li>
            {% if current_section %}
            <li class="breadcrumb-item {% if not current_genre and not current_tag %}active{% endif %}" {% if not current_genre and not current_tag %}aria-current="page"{% endif %}>
                {% if current_genre or current_tag %}
                    <a href="{% url 'reader:section_home' current_language.code current_section.slug %}">{{ current_section.localized_name }}</a>
                {% else %}
                    {{ current_section.localized_name }}
                {% endif %}
            </li>
            {% endif %}
            {% if current_genre %}
            <li class="breadcrumb-item {% if not current_tag %}active{% endif %}" {% if not current_tag %}aria-current="page"{% endif %}>
                {% if current_tag %}
                    <a href="{% url 'reader:section_genre_book_list' current_language.code current_section.slug current_genre.slug %}">{{ current_genre.localized_name }}</a>
                {% else %}
                    {{ current_genre.localized_name }}
                {% endif %}
            </li>
            {% endif %}
            {% if current_tag %}
            <li class="breadcrumb-item active" aria-current="page">
                {{ current_tag.localized_name }}
            </li>
            {% endif %}
        </ol>
    </nav>
    {% endif %}
{% endblock %}
```

2. **Filter Buttons:** Update to use section-aware URLs

```html
<!-- Genre Filter -->
<a href="{% url 'reader:section_genre_book_list' current_language.code current_section.slug genre.slug %}"
   class="btn btn-sm btn-min-width {% if request.GET.genre == genre.slug %}btn-primary-custom{% else %}btn-outline-primary-custom{% endif %}">
    {{ genre.localized_name }}
</a>
```

**Tasks:**
- [ ] Update breadcrumbs with section hierarchy
- [ ] Update filter URLs to be section-aware
- [ ] Update "All Books" link
- [ ] Update empty state link

---

#### 2.3 Update Book Card Partial

**File:** `myapp/reader/templates/reader/partials/book_card.html`

**Changes:**

1. **Book Detail Link (Line 9):** Include section in URL

```html
<a href="{% url 'reader:section_book_detail' current_language.code book.bookmaster.section.slug book.slug %}" class="book-card-link">
```

2. **Modal "Read Now" Button (Line 135):** Include section in URL

```html
<a href="{% url 'reader:section_book_detail' current_language.code book.bookmaster.section.slug book.slug %}" class="btn btn-primary-custom">
    Read Now
</a>
```

**Tasks:**
- [ ] Update book detail URL to include section
- [ ] Update modal "Read Now" button URL
- [ ] Add fallback for books without section (if applicable)

---

#### 2.4 Create Section Home Template

**File:** `myapp/reader/templates/reader/section_home.html` (NEW)

**Purpose:** Landing page for each section showing featured content

**Structure:**

```html
{% extends "reader/base.html" %}
{% load static %}

{% block title %}{{ current_section.localized_name }} - {{ current_language.name }}{% endblock %}

{% block breadcrumb_check %}
    <nav aria-label="breadcrumb" class="d-none d-md-block ms-2">
        <ol class="breadcrumb mb-0">
            <li class="breadcrumb-item"><a href="{% url 'reader:welcome' current_language.code %}">Home</a></li>
            <li class="breadcrumb-item active" aria-current="page">{{ current_section.localized_name }}</li>
        </ol>
    </nav>
{% endblock %}

{% block content %}
<!-- Section Hero -->
<section class="section-hero py-5 mb-4">
    <div class="text-center">
        <h1 class="display-4">{{ current_section.localized_name }}</h1>
        {% if current_section.description %}
        <p class="lead">{{ current_section.description }}</p>
        {% endif %}
    </div>
</section>

<!-- Featured Genres in Section -->
{% if featured_genres %}
<section class="mb-5">
    <h2 class="mb-3">Popular Genres</h2>
    <div class="d-flex flex-wrap gap-2">
        {% for genre in featured_genres %}
        <a href="{% url 'reader:section_genre_book_list' current_language.code current_section.slug genre.slug %}"
           class="btn btn-lg btn-outline-primary-custom">
            {{ genre.localized_name }}
        </a>
        {% endfor %}
    </div>
</section>
{% endif %}

<!-- Recently Updated Books -->
{% if recently_updated %}
<section class="mb-5">
    <div class="d-flex justify-content-between align-items-center mb-3">
        <h2>Recently Updated</h2>
        <a href="{% url 'reader:section_book_list' current_language.code current_section.slug %}" class="btn btn-sm btn-outline-primary-custom">
            View All
        </a>
    </div>
    <div class="book-grid">
        {% for book in recently_updated %}
            {% include "reader/partials/book_card.html" with book=book current_language=current_language %}
        {% endfor %}
    </div>
</section>
{% endif %}

<!-- New Arrivals -->
{% if new_arrivals %}
<section class="mb-5">
    <div class="d-flex justify-content-between align-items-center mb-3">
        <h2>New Arrivals</h2>
        <a href="{% url 'reader:section_book_list' current_language.code current_section.slug %}?status=ongoing" class="btn btn-sm btn-outline-primary-custom">
            View All
        </a>
    </div>
    <div class="book-grid">
        {% for book in new_arrivals %}
            {% include "reader/partials/book_card.html" with book=book current_language=current_language %}
        {% endfor %}
    </div>
</section>
{% endif %}

<!-- Browse All Section Books -->
<section class="text-center py-5">
    <a href="{% url 'reader:section_book_list' current_language.code current_section.slug %}" class="btn btn-lg btn-primary-custom">
        Browse All {{ current_section.localized_name }} Books
    </a>
</section>
{% endblock %}
```

**Tasks:**
- [ ] Create section home template
- [ ] Add section hero section
- [ ] Add featured genres section
- [ ] Add recently updated books section
- [ ] Add new arrivals section
- [ ] Style section-specific content

---

#### 2.5 Update Other Templates

**Files to Update:**

1. **`myapp/reader/templates/reader/welcome.html`**
   - Update section links to use `{% url 'reader:section_home' %}`
   - Update featured book links to include section

2. **`myapp/reader/templates/reader/book_detail.html`**
   - Update breadcrumbs to include section
   - Update chapter links to include section
   - Update "Back to Books" link to use section URL

3. **`myapp/reader/templates/reader/chapter_detail.html`**
   - Update breadcrumbs to include section
   - Update book detail link to include section
   - Update navigation links (previous/next chapter) to include section

4. **`myapp/reader/templates/reader/search.html`**
   - Add section context if searching within section
   - Update result book links to include section

**Tasks:**
- [ ] Update welcome.html section links
- [ ] Update book_detail.html breadcrumbs and links
- [ ] Update chapter_detail.html navigation
- [ ] Update search.html result links

---

### Phase 3: Context Processors & Template Tags

#### 3.1 Update Context Processor

**File:** `myapp/books/context_processors.py`

**Purpose:** Add global context for section-aware URLs

**Implementation:**

```python
def reader_context(request):
    """
    Add reader-specific context to all templates.

    Adds:
    - current_section: Section object if in section view
    - is_section_view: Boolean flag
    """
    context = {}

    # Detect if we're in a section view
    if hasattr(request, 'resolver_match') and request.resolver_match:
        url_name = request.resolver_match.url_name
        kwargs = request.resolver_match.kwargs

        if url_name and url_name.startswith('section_'):
            section_slug = kwargs.get('section_slug')
            if section_slug:
                from books.models import Section
                try:
                    context['current_section'] = Section.objects.get(slug=section_slug)
                    context['is_section_view'] = True
                except Section.DoesNotExist:
                    context['is_section_view'] = False
        else:
            context['is_section_view'] = False

    return context
```

**Tasks:**
- [ ] Update context processor to add `current_section`
- [ ] Add `is_section_view` flag
- [ ] Ensure context processor is registered in settings

---

#### 3.2 Create Template Tags

**File:** `myapp/reader/templatetags/reader_extras.py`

**Purpose:** Helper tags for building section-aware URLs

**Implementation:**

```python
from django import template
from django.urls import reverse

register = template.Library()

@register.simple_tag(takes_context=True)
def book_url(context, book):
    """
    Generate correct book URL with section.

    Usage: {% book_url book %}
    """
    current_language = context.get('current_language')
    if not current_language:
        return '#'

    section = book.bookmaster.section
    if section:
        return reverse(
            'reader:section_book_detail',
            args=[current_language.code, section.slug, book.slug]
        )
    else:
        # Fallback to legacy URL
        return reverse(
            'reader:book_detail',
            args=[current_language.code, book.slug]
        )

@register.simple_tag(takes_context=True)
def chapter_url(context, chapter):
    """
    Generate correct chapter URL with section.

    Usage: {% chapter_url chapter %}
    """
    current_language = context.get('current_language')
    if not current_language:
        return '#'

    book = chapter.book
    section = book.bookmaster.section

    if section:
        return reverse(
            'reader:section_chapter_detail',
            args=[current_language.code, section.slug, book.slug, chapter.slug]
        )
    else:
        # Fallback to legacy URL
        return reverse(
            'reader:chapter_detail',
            args=[current_language.code, book.slug, chapter.slug]
        )

@register.simple_tag(takes_context=True)
def section_book_list_url(context, section=None):
    """
    Generate section book list URL.

    Usage: {% section_book_list_url section %}
    """
    current_language = context.get('current_language')
    if not current_language:
        return '#'

    if section:
        return reverse(
            'reader:section_book_list',
            args=[current_language.code, section.slug]
        )
    else:
        return reverse(
            'reader:browse',
            args=[current_language.code]
        )
```

**Tasks:**
- [ ] Create or update `reader_extras.py`
- [ ] Implement `book_url` template tag
- [ ] Implement `chapter_url` template tag
- [ ] Implement `section_book_list_url` template tag
- [ ] Add documentation for template tags

---

### Phase 4: JavaScript Updates

#### 4.1 Update Reading Tracker

**File:** `myapp/reader/static/reader/js/reading-tracker.js`

**Analysis:** No changes needed - API endpoint is section-agnostic

**Tasks:**
- [ ] Verify reading tracker still works with new URLs
- [ ] Test progress saving on section-based chapter URLs

---

#### 4.2 Add URL Helper (Optional)

**File:** `myapp/reader/static/reader/js/url-helper.js` (NEW - OPTIONAL)

**Purpose:** JavaScript helpers for building section-aware URLs

**Implementation:**

```javascript
/**
 * URL Helper for Section-Aware URLs
 */
const URLHelper = {
    /**
     * Build section-aware URL
     * @param {string} languageCode - Language code (e.g., 'zh', 'en')
     * @param {string} sectionSlug - Section slug (e.g., 'fiction', 'bl')
     * @param {string} path - Path after section (e.g., 'books/', 'book/my-novel/')
     * @returns {string} Complete URL
     */
    buildSectionUrl(languageCode, sectionSlug, path) {
        return `/${languageCode}/${sectionSlug}/${path}`;
    },

    /**
     * Get current section slug from URL
     * @returns {string|null} Section slug or null
     */
    getCurrentSection() {
        const pathParts = window.location.pathname.split('/').filter(p => p);
        if (pathParts.length >= 2) {
            // Pattern: /<language>/<section>/...
            return pathParts[1];
        }
        return null;
    },

    /**
     * Get current language code from URL
     * @returns {string|null} Language code or null
     */
    getCurrentLanguage() {
        const pathParts = window.location.pathname.split('/').filter(p => p);
        if (pathParts.length >= 1) {
            return pathParts[0];
        }
        return null;
    }
};

// Export for use in other scripts
window.URLHelper = URLHelper;
```

**Tasks:**
- [ ] Create URL helper JavaScript (optional)
- [ ] Include in base template if created
- [ ] Update any AJAX calls to use helper

---

### Phase 5: Backward Compatibility & Migration

#### 5.1 Add Redirect Middleware (Optional)

**File:** `myapp/reader/middleware.py` (NEW - OPTIONAL)

**Purpose:** Automatically redirect old URLs to new section-based URLs

**Implementation:**

```python
from django.shortcuts import redirect
from django.urls import reverse
from books.models import Book, Section

class SectionURLRedirectMiddleware:
    """
    Middleware to redirect old query-based URLs to new path-based URLs.

    Examples:
    - /zh/books/?section=fiction → /zh/fiction/books/
    - /zh/book/my-novel/ → /zh/fiction/book/my-novel/
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Check if this is a legacy URL pattern
        path = request.path

        # Redirect /books/?section=X to /section/books/
        if path.endswith('/books/') and 'section' in request.GET:
            section_slug = request.GET.get('section')
            language_code = path.split('/')[1]

            query_params = request.GET.copy()
            query_params.pop('section', None)

            new_url = reverse('reader:section_book_list', args=[language_code, section_slug])
            if query_params:
                new_url += f"?{query_params.urlencode()}"

            return redirect(new_url, permanent=False)

        response = self.get_response(request)
        return response
```

**Tasks:**
- [ ] Create redirect middleware (optional)
- [ ] Add to `MIDDLEWARE` in settings.py
- [ ] Test redirect behavior

---

#### 5.2 Update External Links

**Tasks:**
- [ ] Check database for any hardcoded URLs
- [ ] Update email templates with new URL patterns
- [ ] Update sitemap generation logic
- [ ] Update robots.txt if needed
- [ ] Update any documentation with new URL structure

---

### Phase 6: SEO Enhancements

#### 6.1 Add Meta Tags

**File:** `myapp/reader/templates/reader/base.html`

**Changes:** Add section-aware meta tags

```html
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">

    <!-- Title -->
    <title>{% block title %}{% endblock %} | wereadly</title>

    <!-- Meta Description -->
    <meta name="description" content="{% block meta_description %}Read web novels in multiple languages{% if current_section %} - {{ current_section.localized_name }}{% endif %}{% endblock %}">

    <!-- Canonical URL -->
    <link rel="canonical" href="{% block canonical_url %}{{ request.build_absolute_uri }}{% endblock %}">

    <!-- Open Graph Tags -->
    <meta property="og:title" content="{% block og_title %}{% block title %}{% endblock %} | wereadly{% endblock %}">
    <meta property="og:description" content="{% block og_description %}{% block meta_description %}{% endblock %}{% endblock %}">
    <meta property="og:url" content="{{ request.build_absolute_uri }}">
    <meta property="og:type" content="website">

    {% if current_section %}
    <meta property="og:section" content="{{ current_section.localized_name }}">
    {% endif %}

    <!-- ... rest of head ... -->
</head>
```

**Tasks:**
- [ ] Add section-aware meta descriptions
- [ ] Add canonical URLs
- [ ] Add Open Graph tags
- [ ] Add Twitter Card tags (optional)

---

#### 6.2 Update Sitemap

**File:** `myapp/reader/sitemaps.py` (NEW or UPDATE)

**Implementation:**

```python
from django.contrib.sitemaps import Sitemap
from books.models import Book, Section, Language

class SectionSitemap(Sitemap):
    """Sitemap for section home pages"""
    changefreq = "daily"
    priority = 0.8

    def items(self):
        sections = Section.objects.all()
        languages = Language.objects.filter(is_public=True)

        # Generate (section, language) pairs
        items = []
        for section in sections:
            for language in languages:
                items.append((section, language))
        return items

    def location(self, item):
        section, language = item
        return f"/{language.code}/{section.slug}/"

class SectionBookSitemap(Sitemap):
    """Sitemap for books with section URLs"""
    changefreq = "weekly"
    priority = 0.6

    def items(self):
        return Book.objects.filter(is_public=True).select_related(
            'bookmaster__section', 'language'
        )

    def location(self, book):
        return f"/{book.language.code}/{book.bookmaster.section.slug}/book/{book.slug}/"

    def lastmod(self, book):
        return book.updated_at
```

**URLs Configuration:**

```python
# In urls.py
from django.contrib.sitemaps.views import sitemap
from reader.sitemaps import SectionSitemap, SectionBookSitemap

sitemaps = {
    'sections': SectionSitemap,
    'books': SectionBookSitemap,
}

urlpatterns = [
    # ... other patterns ...
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='sitemap'),
]
```

**Tasks:**
- [ ] Create or update sitemap classes
- [ ] Generate section-based sitemaps
- [ ] Test sitemap.xml output
- [ ] Submit to Google Search Console

---

#### 6.3 Add Structured Data

**File:** `myapp/reader/templates/reader/base.html` or individual templates

**Implementation:** Add JSON-LD structured data

```html
{% block structured_data %}
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "BreadcrumbList",
  "itemListElement": [
    {
      "@type": "ListItem",
      "position": 1,
      "name": "Home",
      "item": "{{ request.scheme }}://{{ request.get_host }}{% url 'reader:welcome' current_language.code %}"
    }
    {% if current_section %}
    ,{
      "@type": "ListItem",
      "position": 2,
      "name": "{{ current_section.localized_name }}",
      "item": "{{ request.scheme }}://{{ request.get_host }}{% url 'reader:section_home' current_language.code current_section.slug %}"
    }
    {% endif %}
  ]
}
</script>
{% endblock %}
```

**Tasks:**
- [ ] Add BreadcrumbList schema
- [ ] Add Book schema on book detail pages
- [ ] Add Organization schema in footer
- [ ] Test with Google Rich Results Test

---

## File Changes Summary

### Files to Create

| File | Purpose |
|------|---------|
| `myapp/reader/mixins.py` | SectionMixin for view classes |
| `myapp/reader/templates/reader/section_home.html` | Section landing page template |
| `myapp/reader/static/reader/js/url-helper.js` | URL building helpers (optional) |
| `myapp/reader/middleware.py` | Redirect middleware (optional) |
| `myapp/reader/sitemaps.py` | Section-aware sitemaps |
| `myapp/reader/templatetags/reader_extras.py` | Template tags (if doesn't exist) |

### Files to Modify

| File | Changes |
|------|---------|
| `myapp/reader/urls.py` | Add section-scoped URL patterns, legacy redirects |
| `myapp/reader/views.py` | Add section-scoped view classes, redirect views |
| `myapp/reader/templates/reader/base.html` | Update navigation, search, offcanvas menu |
| `myapp/reader/templates/reader/book_list.html` | Update breadcrumbs, filters, links |
| `myapp/reader/templates/reader/book_detail.html` | Update breadcrumbs, navigation |
| `myapp/reader/templates/reader/chapter_detail.html` | Update navigation, links |
| `myapp/reader/templates/reader/welcome.html` | Update section links |
| `myapp/reader/templates/reader/search.html` | Add section context |
| `myapp/reader/templates/reader/partials/book_card.html` | Update book detail URLs |
| `myapp/books/context_processors.py` | Add section context (optional) |
| `myapp/myapp/settings.py` | Register middleware if using (optional) |

---

## Testing Plan

### Manual Testing Checklist

#### URL Routing
- [ ] `/zh/fiction/` loads SectionHomeView
- [ ] `/zh/fiction/books/` shows fiction books only
- [ ] `/zh/fiction/genre/cultivation/` filters by genre within section
- [ ] `/zh/bl/book/my-novel/` shows book detail with BL section context
- [ ] `/en/gl/book/her-story/chapter-1/` shows chapter with GL section context
- [ ] Invalid section slug returns 404

#### Section Filtering
- [ ] Books shown belong to correct section
- [ ] Genre filtering works within section
- [ ] Tag filtering works within section
- [ ] Status filtering works within section
- [ ] Multiple filters can be combined

#### Search
- [ ] Global search (`/zh/search/`) searches all sections
- [ ] Section search (`/zh/fiction/search/`) searches within section
- [ ] Search preserves section context in results
- [ ] Search results link to correct section URLs

#### Navigation
- [ ] Section navigation bar highlights current section
- [ ] Breadcrumbs show correct hierarchy
- [ ] Language switcher preserves section context
- [ ] Offcanvas menu links to correct section/genre URLs
- [ ] Book cards link to section-scoped book detail

#### Backward Compatibility
- [ ] `/zh/books/` redirects appropriately
- [ ] `/zh/books/?section=fiction` redirects to `/zh/fiction/books/`
- [ ] Old book detail URLs redirect to section-scoped URLs
- [ ] Query parameters are preserved in redirects

#### Permissions & Edge Cases
- [ ] Non-public sections (if implemented)
- [ ] Books without sections (fallback behavior)
- [ ] Genres from different sections (404 or redirect)
- [ ] Missing language code (404)
- [ ] Missing section slug (404)

#### Mobile Responsiveness
- [ ] Section navigation works on mobile
- [ ] Breadcrumbs readable on mobile
- [ ] Search works on mobile
- [ ] All links clickable on mobile

#### Performance
- [ ] Page load times reasonable
- [ ] No N+1 queries introduced
- [ ] Caching still effective
- [ ] Database query count acceptable

---

### Automated Testing (Optional)

Create Django tests in `myapp/reader/tests/test_section_urls.py`:

```python
from django.test import TestCase, Client
from django.urls import reverse
from books.models import Section, Language, Book, BookMaster

class SectionURLTestCase(TestCase):
    def setUp(self):
        # Create test data
        self.language = Language.objects.create(code='en', name='English')
        self.section = Section.objects.create(slug='fiction', name='Fiction')
        # ... create test books, etc.

    def test_section_home_url(self):
        """Test section home page loads"""
        url = reverse('reader:section_home', args=['en', 'fiction'])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_section_book_list_url(self):
        """Test section book list filters by section"""
        url = reverse('reader:section_book_list', args=['en', 'fiction'])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        # Assert books are filtered by section

    def test_invalid_section_returns_404(self):
        """Test invalid section returns 404"""
        url = reverse('reader:section_home', args=['en', 'invalid'])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_legacy_url_redirects(self):
        """Test old URL redirects to new section URL"""
        response = self.client.get('/en/books/?section=fiction')
        self.assertRedirects(response, '/en/fiction/books/', status_code=302)

    # ... more tests
```

**Tasks:**
- [ ] Create test file
- [ ] Write URL routing tests
- [ ] Write view tests
- [ ] Write redirect tests
- [ ] Run tests: `python manage.py test reader.tests.test_section_urls`

---

## Rollout Strategy

### Option A: Big Bang (Recommended for Small User Base)

**Timeline:** 1-2 days

1. **Day 1 - Implementation:**
   - Implement all backend changes (Phase 1)
   - Implement all frontend changes (Phase 2)
   - Add redirects for backward compatibility
   - Test thoroughly in development

2. **Day 1 Evening - Deploy:**
   - Deploy to production
   - Monitor error logs
   - Test all critical paths

3. **Day 2 - Monitor:**
   - Watch for 404 errors
   - Fix any broken links
   - User feedback collection

**Pros:**
- ✅ Fast implementation
- ✅ Clean cutover
- ✅ Easier to manage

**Cons:**
- ❌ Higher risk
- ❌ Potential for broken links
- ❌ User confusion if issues occur

---

### Option B: Gradual Migration

**Timeline:** 2-3 weeks

1. **Week 1 - Dual URLs:**
   - Deploy new section URLs
   - Keep old URLs working (no redirects yet)
   - Add new links in UI but keep old ones as fallback
   - Test in production with real users

2. **Week 2 - Transition:**
   - Update all links to use new URLs
   - Add temporary redirects (302)
   - Monitor 404s and fix broken links
   - Collect user feedback

3. **Week 3 - Finalize:**
   - Change redirects to permanent (301)
   - Remove old URL patterns
   - Update documentation
   - Announce new URL structure

**Pros:**
- ✅ Lower risk
- ✅ Time to fix issues
- ✅ Gradual user adaptation

**Cons:**
- ❌ Longer timeline
- ❌ More complex maintenance
- ❌ Duplicate URL patterns temporarily

---

### Recommended Approach

**For this project:** Use **Option A (Big Bang)** because:
- Small user base
- Easy rollback (keep old URLs as fallback)
- Cleaner codebase
- Faster time to completion

**Rollback Plan:**
1. Keep old URL patterns in code (commented out)
2. If issues occur, uncomment old patterns
3. Comment out new patterns
4. Redeploy (< 5 minutes)

---

## Estimated Effort

| Phase | Tasks | Effort | Priority |
|-------|-------|--------|----------|
| **Phase 1: Backend** | URL patterns, views, mixins, redirects | 3-4 hours | **HIGH** |
| **Phase 2: Frontend** | Templates, breadcrumbs, navigation | 2-3 hours | **HIGH** |
| **Phase 3: Context & Tags** | Context processors, template tags | 1 hour | **MEDIUM** |
| **Phase 4: JavaScript** | URL helpers (optional) | 30 mins | **LOW** |
| **Phase 5: Compatibility** | Redirects, migration | 1 hour | **MEDIUM** |
| **Phase 6: SEO** | Meta tags, sitemap, structured data | 1-2 hours | **LOW** |
| **Testing** | Manual + automated testing | 2 hours | **HIGH** |
| **Documentation** | Update docs, comments | 1 hour | **MEDIUM** |
| **Deployment** | Deploy, monitor, fix issues | 1-2 hours | **HIGH** |
| **TOTAL** | | **12-16 hours** | |

---

## Decision Points

Before implementation, decide on:

### 1. Cross-Section Browsing

**Question:** Should users be able to browse all books across sections?

**Options:**
- **A:** Keep `/browse/` URL for all books (recommended)
- **B:** Remove cross-section browsing (force section selection)
- **C:** Make welcome page the browse page

**Recommendation:** **Option A** - Keep `/zh/browse/` for power users who want to see everything

---

### 2. Section Home Pages

**Question:** Should sections have dedicated home pages?

**Options:**
- **A:** Create section home pages with featured content (recommended)
- **B:** Redirect `/zh/fiction/` to `/zh/fiction/books/` immediately

**Recommendation:** **Option A** - Section home pages improve UX and SEO

---

### 3. Redirect Strategy

**Question:** Should redirects be permanent or temporary during migration?

**Options:**
- **A:** Temporary (302) during testing, then permanent (301)
- **B:** Permanent (301) immediately
- **C:** No redirects, just show 404 and let users adapt

**Recommendation:** **Option A** - Start with 302, switch to 301 after 1 week

---

### 4. Books Without Sections

**Question:** How to handle books without a section assigned?

**Options:**
- **A:** Hide from section views, only show in browse all
- **B:** Create default "General" section
- **C:** Return 404 for legacy book URLs

**Recommendation:** **Option B** - Create a "General" or "Uncategorized" section as fallback

---

### 5. Genre Cross-Section Linking

**Question:** What happens if user tries to access genre from wrong section?

**Example:** `/zh/bl/genre/cultivation/` (cultivation is fiction genre, not BL)

**Options:**
- **A:** Return 404 (recommended for data integrity)
- **B:** Redirect to correct section
- **C:** Show empty results

**Recommendation:** **Option A** - Validates data consistency

---

### 6. Language Switcher Behavior

**Question:** Should language switcher preserve section context?

**Options:**
- **A:** Yes, stay in same section when switching language (recommended)
- **B:** No, go to welcome page for new language

**Recommendation:** **Option A** - Better UX

**Implementation:**
```python
# In language switcher template
<a href="{% url 'reader:section_home' lang.code current_section.slug %}">
    {{ lang.local_name }}
</a>
```

---

## Next Steps

### Ready to Implement?

1. **Review this plan** with your team
2. **Make decisions** on the 6 decision points above
3. **Set up development environment** with test data
4. **Begin Phase 1** (Backend implementation)
5. **Test each phase** before moving to next
6. **Deploy gradually** or all at once (based on rollout strategy)

### Questions to Answer Before Starting

- [ ] Which rollout strategy? (Big Bang vs Gradual)
- [ ] Should we create section home pages?
- [ ] Should we keep `/browse/` for cross-section browsing?
- [ ] How to handle books without sections?
- [ ] Temporary (302) or permanent (301) redirects?
- [ ] Should language switcher preserve section?

---

## Support & Resources

### Documentation to Update

- [ ] User guide (how to navigate new URLs)
- [ ] Developer docs (URL patterns)
- [ ] API documentation (if applicable)
- [ ] README.md

### Monitoring After Deployment

- [ ] Monitor 404 errors in logs
- [ ] Track page load performance
- [ ] Watch database query counts
- [ ] Collect user feedback
- [ ] Check Google Search Console for crawl errors

---

## Summary

This plan converts your current query-based section filtering to a clean, SEO-friendly section-based URL structure:

**Before:** `/zh/books/?section=fiction`
**After:** `/zh/fiction/books/`

**Key Benefits:**
- ✅ Better SEO with semantic URLs
- ✅ Clearer content hierarchy
- ✅ Improved user experience
- ✅ Easier to bookmark and share
- ✅ Dedicated section landing pages

**Estimated Timeline:** 12-16 hours of development + 2-4 hours testing/deployment

---

**Ready to start? Let me know which phase you'd like to implement first!**
