# Author Integration in Reader App - Implementation Plan

## Overview

Integrate the existing `Author` model (from `books.models.taxonomy`) into the reader app:
1. Update book detail view to display author with link
2. Create new author detail view showing author info and related books

## Current State

- **Author Model**: `books/models/taxonomy.py:354` - Has `name`, `slug`, `description`, `translations`, `avatar` fields
- **BookMaster.author**: FK to Author (`books/models/core.py:113`)
- **Book.author**: CharField (legacy, language-specific author name) - keep for backward compatibility
- **Book Detail Template**: `myapp/reader/templates/reader/book_detail.html:26-28` - Currently uses `book.author` (CharField)

## Implementation Tasks

### 1. Update Book Detail View

**File**: `myapp/reader/views/detail_views.py`

Changes to `BookDetailView.get_queryset()`:
- Add `bookmaster__author` to `select_related()`

Changes to `BookDetailView.get_context_data()`:
- Add author context with localized name

**File**: `myapp/reader/views/section_views.py`

Apply same changes to `SectionBookDetailView`.

### 2. Update Book Detail Template

**File**: `myapp/reader/templates/reader/book_detail.html`

Replace lines 26-28:
```html
{% if book.bookmaster.author %}
<p class="lead mb-3">
    by <a href="{% url 'reader:section_author_detail' current_language.code book.bookmaster.section.slug book.bookmaster.author.slug %}">
        {{ author_localized_name }}
    </a>
</p>
{% elif book.author %}
<p class="lead mb-3">by {{ book.author }}</p>
{% endif %}
```

### 3. Create Author Detail View

**File**: `myapp/reader/views/detail_views.py`

Add new `AuthorDetailView` class:
```python
class AuthorDetailView(BaseReaderView, DetailView):
    """
    Author detail page showing author info and their books.
    """
    template_name = "reader/author_detail.html"
    model = Author
    context_object_name = "author"
    slug_field = "slug"
    slug_url_kwarg = "author_slug"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        language = self.get_language()

        # Localized author info
        context['author_name'] = self.object.get_localized_name(language.code)
        context['author_description'] = self.object.get_localized_description(language.code)

        # Get author's books (published in current language)
        context['books'] = Book.objects.filter(
            bookmaster__author=self.object,
            language=language,
            is_public=True
        ).select_related('bookmaster', 'bookmaster__section').order_by('-created_at')

        return context
```

Add section-scoped version `SectionAuthorDetailView` that also validates section.

### 4. Create Author Detail Template

**File**: `myapp/reader/templates/reader/author_detail.html`

```html
{% extends "reader/base.html" %}
{% load humanize %}
{% load books_extras %}

{% block title %}{{ author_name }}{% endblock %}

{% block content %}
<div class="row mt-2">
    <div class="col-lg-8">
        <h1 class="display-5 mb-3">{{ author_name }}</h1>

        {% if author_description %}
        <div class="mb-4">
            <p class="text-muted">{{ author_description|linebreaks }}</p>
        </div>
        {% endif %}

        <h3 class="mb-4">Books by {{ author_name }}</h3>

        {% if books %}
        <div class="row">
            {% for book in books %}
            {% include "reader/partials/book_card.html" %}
            {% endfor %}
        </div>
        {% else %}
        <p class="text-muted">No published books available.</p>
        {% endif %}
    </div>

    <div class="col-lg-4">
        {% if author.avatar %}
        <div class="card mb-4">
            <img src="{{ author.avatar.url }}" class="card-img-top" alt="{{ author_name }}">
        </div>
        {% endif %}
    </div>
</div>
{% endblock %}
```

### 5. Add URL Routes

**File**: `myapp/reader/urls.py`

Add under section-scoped URLs:
```python
# Section author detail
path(
    "<str:language_code>/<slug:section_slug>/author/<slug:author_slug>/",
    views.SectionAuthorDetailView.as_view(),
    name="section_author_detail",
),
```

Add global author URL (optional, for authors with books across sections):
```python
# Global author page
path(
    "<str:language_code>/author/<slug:author_slug>/",
    views.AuthorDetailView.as_view(),
    name="author_detail",
),
```

### 6. Update Views __init__.py

**File**: `myapp/reader/views/__init__.py`

Export new views:
```python
from .detail_views import AuthorDetailView, SectionAuthorDetailView
```

## File Changes Summary

| File | Action |
|------|--------|
| `myapp/reader/views/detail_views.py` | Modify queryset, add AuthorDetailView |
| `myapp/reader/views/section_views.py` | Modify SectionBookDetailView, add SectionAuthorDetailView |
| `myapp/reader/views/__init__.py` | Export new views |
| `myapp/reader/templates/reader/book_detail.html` | Update author display with link |
| `myapp/reader/templates/reader/author_detail.html` | Create new template |
| `myapp/reader/urls.py` | Add author URL routes |

## Additional Tasks

1. **Book card partial**: Update to show author link in Modal (`partials/book_card.html`)
2. **SEO**: Add structured data (JSON-LD) for author pages
