# Book Meta Partial Implementation Plan

## Overview

Create a reusable `book_meta.html` partial that displays taxonomy badges (Section, Genres, Tags, Entities) with different color schemes and configurable visibility. This partial will be used in:
1. **Book Detail Page** - Full display of all taxonomy
2. **Book Card Modal** - Full display in modal popup
3. **Book Card** - Partial display (section visibility conditional)

## Design Specifications

### Badge Color Scheme
| Taxonomy Type | Badge Class | Color |
|---------------|-------------|-------|
| Section | `bg-primary-custom` | Orange (#ff6b35) |
| Genre (all) | `bg-primary` | Blue (Bootstrap primary) |
| Tags | `bg-secondary` | Gray (Bootstrap secondary) |
| Entities (all types) | `border text-secondary` | Gray outline |

### Visibility Configuration
The partial will accept parameters to control what's displayed:
- `show_section` - Whether to show section badge (default: True)
- `show_genres` - Whether to show genre badges (default: True)
- `show_tags` - Whether to show tag badges (default: True)
- `show_entities` - Whether to show entity badges (default: False)
- `max_genres` - Maximum genres to display (None = all)
- `max_tags` - Maximum tags per category (None = all)
- `max_entities` - Maximum entities to display (None = all)
- `compact` - Compact mode for book cards (smaller font, tighter spacing)
- `show_hierarchy` - Show parent > child hierarchy for genres (default: True)

## Implementation Steps

### Step 1: Create the Book Meta Partial Template
**File**: `myapp/reader/templates/reader/partials/book_meta.html`

```django
{% comment %}
Book Meta Partial - Displays taxonomy badges for books

Required Context:
- book: Book object with bookmaster relationship
- current_language: Language object (for URLs)

Optional Context (passed via include):
- show_section: bool (default True)
- show_genres: bool (default True)
- show_tags: bool (default True)
- show_entities: bool (default False)
- max_genres: int (default None = all)
- max_tags: int (default None = all)
- max_entities: int (default None = all)
- compact: bool (default False)
- show_hierarchy: bool (default True)

Usage:
{% include "reader/partials/book_meta.html" with show_section=False compact=True %}
{% endcomment %}
```

**Structure**:
```html
<div class="book-meta {% if compact %}book-meta-compact{% endif %}">
  <!-- Section Badge -->
  <!-- Genre Badges -->
  <!-- Tag Badges (grouped by category) -->
  <!-- Entity Badges (grouped by type) -->
</div>
```

### Step 2: Add CSS Styles
**File**: `myapp/reader/static/reader/css/styles.css`

Add new styles for:
- `.book-meta` - Container class
- `.book-meta-compact` - Compact variant (smaller fonts, tighter spacing)
- Entity outline badge styling
- Consistent spacing and wrapping

### Step 3: Update Book Card Template
**File**: `myapp/reader/templates/reader/partials/book_card.html`

Replace inline taxonomy display with:
```django
{% include "reader/partials/book_meta.html" with show_section=show_section|default:True show_tags=False show_entities=False max_genres=2 compact=True %}
```

Update modal section to use:
```django
{% include "reader/partials/book_meta.html" with show_tags=False show_entities=False %}
```

### Step 4: Update Book Detail Template
**File**: `myapp/reader/templates/reader/book_detail.html`

Replace inline taxonomy section with:
```django
{% include "reader/partials/book_meta.html" with show_entities=True %}
```

### Step 5: Update Views to Pass Entity Context
**File**: `myapp/reader/views/base.py` (BaseBookDetailView)

Add entities to context:
```python
# In get_context_data
entities = self.object.bookmaster.entities.all()
context["entities"] = entities
context["entities_by_type"] = self._group_entities_by_type(entities, language_code)
```

### Step 6: Update Book List Views
For views that render book cards, add `show_section` to context based on view type:
- Welcome page: `show_section=True`
- Section page: `show_section=False`

## Files to Modify

| File | Action | Description |
|------|--------|-------------|
| `myapp/reader/templates/reader/partials/book_meta.html` | Create | New partial template |
| `myapp/reader/templates/reader/partials/book_card.html` | Modify | Use book_meta partial |
| `myapp/reader/templates/reader/book_detail.html` | Modify | Use book_meta partial |
| `myapp/reader/static/reader/css/styles.css` | Modify | Add book-meta styles |
| `myapp/reader/views/base.py` | Modify | Add entities to context |
| `myapp/reader/views/section_views.py` | Modify | Pass show_section=False |

## Template Usage Examples

### In Welcome Page (show section)
```django
{% for book in featured_books %}
    {% include "reader/partials/book_card.html" with show_section=True %}
{% endfor %}
```

### In Section Page (hide section)
```django
{% for book in books %}
    {% include "reader/partials/book_card.html" with show_section=False %}
{% endfor %}
```

### In Book Detail Page
```django
{% include "reader/partials/book_meta.html" with show_entities=True %}
```

### In Book Card Modal
```django
{% include "reader/partials/book_meta.html" with show_tags=False %}
```

## Detailed Partial Structure

```django
{# book_meta.html #}
{% load reader_tags %}

{% with show_section=show_section|default:True show_genres=show_genres|default:True show_tags=show_tags|default:True show_entities=show_entities|default:False compact=compact|default:False show_hierarchy=show_hierarchy|default:True %}

<div class="book-meta {% if compact %}book-meta-compact{% endif %}">

    {# SECTION BADGE #}
    {% if show_section and section %}
    <div class="book-meta-section mb-2">
        <a href="{% url 'reader:section_home' current_language.code section.slug %}"
           class="badge bg-primary-custom text-decoration-none">
            {% if section.icon %}<i class="{{ section.icon }} me-1"></i>{% endif %}
            {{ section_localized_name }}
        </a>
    </div>
    {% endif %}

    {# GENRE BADGES - Blue (Bootstrap primary) #}
    {% if show_genres and genres %}
    <div class="book-meta-genres mb-2">
        <div class="d-flex flex-wrap gap-1">
            {% for genre in genres|slice:max_genres %}
            <a href="{% url 'reader:section_genre_book_list' current_language.code section.slug genre.slug %}"
               class="badge bg-primary text-decoration-none">
                {% if show_hierarchy and genre.parent_localized_name %}
                    {{ genre.parent_localized_name }} &rsaquo;
                {% endif %}
                {{ genre.localized_name }}
            </a>
            {% endfor %}
        </div>
    </div>
    {% endif %}

    {# TAG BADGES - Gray (Bootstrap secondary) #}
    {% if show_tags and tags_by_category %}
    <div class="book-meta-tags mb-2">
        {% for category, tags in tags_by_category.items %}
        <div class="mb-1">
            {% if not compact %}<small class="text-muted d-block mb-1">{{ category }}</small>{% endif %}
            <div class="d-flex flex-wrap gap-1">
                {% for tag in tags|slice:max_tags %}
                <a href="{% url 'reader:section_tag_book_list' current_language.code section.slug tag.slug %}"
                   class="badge bg-secondary text-decoration-none">
                    {{ tag.localized_name }}
                </a>
                {% endfor %}
            </div>
        </div>
        {% endfor %}
    </div>
    {% endif %}

    {# ENTITY BADGES - Gray outline (all types) #}
    {% if show_entities and entities_by_type %}
    <div class="book-meta-entities">
        {% for type, entities in entities_by_type.items %}
        <div class="mb-1">
            {% if not compact %}<small class="text-muted d-block mb-1">{{ type }}</small>{% endif %}
            <div class="d-flex flex-wrap gap-1">
                {% for entity in entities|slice:max_entities %}
                <span class="badge border text-secondary bg-transparent">
                    {{ entity.localized_name|default:entity.source_name }}
                </span>
                {% endfor %}
            </div>
        </div>
        {% endfor %}
    </div>
    {% endif %}

</div>

{% endwith %}
```

## CSS Additions

```css
/* Book Meta Partial Styles */
.book-meta {
    display: flex;
    flex-direction: column;
}

.book-meta .badge {
    font-size: 0.85rem;
    padding: 0.4rem 0.8rem;
}

.book-meta-compact .badge {
    font-size: 0.7rem;
    padding: 0.25rem 0.5rem;
}

.book-meta-compact .mb-2 {
    margin-bottom: 0.5rem !important;
}

/* Entity outline badge */
.book-meta .badge.border.bg-transparent {
    border-color: #6c757d !important;
}

/* Dark mode support */
[data-theme="dark"] .book-meta .badge.border.bg-transparent {
    border-color: #aaa !important;
    color: #aaa !important;
}
```

## Testing Checklist

- [ ] Book meta partial renders correctly in book detail page
- [ ] Book meta partial renders correctly in book card modal
- [ ] Book meta partial renders correctly in book card (compact mode)
- [ ] Section badge hidden when `show_section=False`
- [ ] Genre slicing works with `max_genres` parameter
- [ ] Tag slicing works with `max_tags` parameter
- [ ] Entity badges display with gray outline
- [ ] Dark mode styling works correctly
- [ ] Links navigate to correct filtered views
- [ ] Localization works for all taxonomy types

## Notes

- The `slice` filter with `None` or undefined value shows all items
- Views need to ensure `section`, `genres`, `tags_by_category` are in context
- Entity support requires updating BaseBookDetailView
- Consider caching entity queries for performance
