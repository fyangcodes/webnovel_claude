# Webnovel Claude - Codebase Exploration Summary

## 1. CURRENT BOOK_CARD STRUCTURE

### File: `/home/user/code/webnovel_claude/myapp/reader/templates/reader/partials/book_card.html`

The book card is a partial template (lines 1-159) that displays:

**Layout:**
- Wrapper: `<div class="book-card">` 
- Link to detail page (context-aware routing based on section)
- Image wrapper with:
  - Book cover image
  - Status badge (Ongoing/Completed) - top-right position
  - Info button (Font Awesome icon) - triggers modal

**Content:**
- Book title (h3.book-card-title)
- Taxonomy section (lines 32-41):
  - Section badge (bg-primary-custom)
  - Up to 2 genres with sliced queryset (bg-secondary)
  - Both use font-size: 0.7rem
  
- Stats section (lines 44-51):
  - Chapter count with icon
  - Total views with icon (if available)

**Modal Implementation (lines 55-158):**
- Bootstrap modal with unique ID: `bookModal{{ book.id }}`
- Modal structure:
  - Header with close button
  - Body divided into:
    - Left column (col-md-4):
      - Book cover image
      - Section badge
      - All genres with parent hierarchy (badge bg-secondary)
    - Right column (col-md-8):
      - Title and author
      - Description
      - Stats grid (Chapters, Status, Views)
  - Footer with Close and Read Now buttons

**Key CSS Classes Used:**
- `book-card`, `book-card-link`, `book-card-image-wrapper`, `book-card-image`
- `badge bg-primary` (status), `badge bg-primary-custom` (section), `badge bg-secondary` (genres)
- `book-card-info-btn`
- `modal-*` classes (Bootstrap)
- `stat-item`, `stat-label`, `stat-value`

---

## 2. CURRENT BOOK_DETAIL STRUCTURE

### File: `/home/user/code/webnovel_claude/myapp/reader/templates/reader/book_detail.html`

**Main Layout:**
- Two-column: Main content (col-lg-8) + Sidebar (col-lg-4)

**Main Content Section (lines 20-144):**

**Book Info (lines 23-68):**
- Title (h1.display-5)
- Author with link
- Stats (lines 37-62):
  - Chapters count
  - Total words
  - Total views
  - Progress status
  - Last update timestamp
- Description (multiline)

**Taxonomy Section (lines 70-142):**
- **Section** (lines 73-82):
  - Single badge with icon
  - Link to section home
  - bg-primary-custom styling
  - Padding: 0.5rem 1rem, font-size: 0.9rem

- **Genres** (lines 86-112):
  - All genres displayed (not sliced)
  - Each linked to genre book list
  - Shows parent > child hierarchy
  - bg-secondary styling
  - Padding: 0.4rem 0.8rem, font-size: 0.85rem
  - Flex wrap layout with gap-2

- **Tags by Category** (lines 116-142):
  - Grouped by tag.category
  - Category name shown as small header
  - All tags displayed
  - bg-light text-dark with border
  - Padding: 0.3rem 0.7rem, font-size: 0.8rem
  - Links to tag book list (section-aware or global)

**Sidebar (lines 148-154):**
- Book cover image (max-height: 400px)

**Chapters Section (lines 157-222):**
- List of published chapters
- 20 chapters per page (paginated)
- Simple pagination with "1...prev page curr page...last"

---

## 3. EXISTING BADGE/TAG STYLING PATTERNS

### CSS Variables (from `/home/user/code/webnovel_claude/myapp/reader/static/reader/css/styles.css`)

```css
:root {
    --color-primary: #ff6b35;
    --color-primary-hover: #ff8555;
    --color-text: #333;
    --color-text-light: #6c757d;
    --color-border: #dee2e6;
}

[data-theme="dark"] {
    --color-primary: #ff9670;
    --color-text: #d4d4d4;
    --color-text-light: #aaa;
}
```

### Badge Classes (Bootstrap + Custom):

**Primary Custom (Sections):**
- Class: `bg-primary-custom`
- Background: `var(--color-primary)` (#ff6b35)
- Color: `#fff` (white text)
- Usage: Sections, Main badges

**Secondary (Genres):**
- Class: `bg-secondary`
- Bootstrap default styling
- Usage: Genre badges

**Light with Border (Tags):**
- Class: `bg-light text-dark border`
- Background: Light color
- Text: Dark
- Border: 1px solid
- Usage: Individual tags

### Modal Styles (lines 286-333):
```css
.modal-content {
    background-color: var(--color-bg);
    border: 1px solid var(--color-border);
    color: var(--color-text);
}

.modal-book-title { color: var(--color-text); }
.modal-book-author { color: var(--color-text-light); }
.modal-book-description { color: var(--color-text); }

.stat-item { color: var(--color-text); }
.stat-label { color: var(--color-text-light); font-weight: 600; }
.stat-value { color: var(--color-text); font-weight: 700; }
```

---

## 4. MODEL RELATIONSHIPS FOR SECTION, GENRE, TAG, ENTITIES

### BookMaster Model (Primary Entity)
Located: `/home/user/code/webnovel_claude/myapp/books/models/core.py:61-208`

**Relationships:**
```
BookMaster
├── section (FK to Section) - nullable
├── genres (M2M through BookGenre, no direct FK)
├── tags (M2M through BookTag, no direct FK)
└── author (FK to Author) - nullable
```

### Section Model
Located: `/home/user/code/webnovel_claude/myapp/books/models/taxonomy.py:23-65`

**Fields:**
- `name` (CharField, unique) - e.g., "Fiction", "BL", "GL"
- `slug` (SlugField, unique)
- `order` (PositiveSmallIntegerField)
- `is_mature` (BooleanField)
- `translations` (JSONField) - from LocalizationModel
- `description` (TextField) - from LocalizationModel

**Reverse Relations:**
- `bookmasters` - All books in this section
- `genres` - All genres belonging to this section

**Localization Methods:**
- `get_localized_name(language_code)` - Returns translated name
- `get_localized_description(language_code)` - Returns translated description

### Genre Model
Located: `/home/user/code/webnovel_claude/myapp/books/models/taxonomy.py:67-176`

**Fields:**
- `name` (CharField) - Can repeat across sections
- `slug` (SlugField) - Unique within section
- `section` (FK to Section) - nullable temporarily
- `parent` (FK to self) - For hierarchical structure
- `is_primary` (BooleanField) - True for main genres, False for sub-genres
- `translations` (JSONField) - from LocalizationModel

**Constraints:**
- Unique together: [section, slug]
- Rules enforced in clean():
  1. Primary genres cannot have parents
  2. Sub-genres must have a primary parent
  3. Parent must be in same section
  4. No self-references or circular references

**Reverse Relations:**
- `sub_genres` - Sub-genres of this genre (if is_primary=True)
- `book_genres` - BookGenre through records
- `parent_genre` - The parent of this genre (if is_primary=False)

**Localization:**
- `get_localized_name(language_code)` - Inherited from LocalizationModel

### BookGenre Through Model
Located: `/home/user/code/webnovel_claude/myapp/books/models/taxonomy.py:178-219`

**Fields:**
- `bookmaster` (FK to BookMaster)
- `genre` (FK to Genre)
- `order` (PositiveSmallIntegerField) - Display order

**Constraints:**
- Unique together: [bookmaster, genre]
- Validation: Genre must belong to BookMaster's section

### Tag Model
Located: `/home/user/code/webnovel_claude/myapp/books/models/taxonomy.py:221-263`

**Fields:**
- `name` (CharField, unique) - e.g., "Female Lead", "System"
- `slug` (SlugField, unique)
- `category` (CharField) - From TagCategory choices
- `translations` (JSONField) - from LocalizationModel

**Categories Available:**
- PROTAGONIST: "Protagonist Type"
- NARRATIVE: "Narrative Style"
- THEME: "Theme"
- TROPE: "Trope"
- CONTENT_WARNING: "Content Warning"
- AUDIENCE: "Target Audience"
- SETTING: "Setting"

**Localization:**
- `get_localized_name(language_code)` - Inherited

### BookTag Through Model
Located: `/home/user/code/webnovel_claude/myapp/books/models/taxonomy.py:265-302`

**Fields:**
- `bookmaster` (FK to BookMaster)
- `tag` (FK to Tag)
- `confidence` (FloatField) - For AI-suggested tags (0.0-1.0)
- `source` (CharField) - From TagSource choices:
  - MANUAL: "Manual"
  - AI_SUGGESTED: "AI Suggested"
  - AI_AUTO: "AI Automatic"
  - COMMUNITY: "Community"

**Constraints:**
- Unique together: [bookmaster, tag]

### Author Model
Located: `/home/user/code/webnovel_claude/myapp/books/models/taxonomy.py:354-393`

**Fields:**
- `name` (CharField, unique)
- `slug` (SlugField, unique)
- `avatar` (ImageField) - nullable
- `translations` (JSONField) - from LocalizationModel

**Reverse Relations:**
- `bookmasters` - All books authored by this author

### BookEntity Model (Named Entities)
Located: `/home/user/code/webnovel_claude/myapp/books/models/context.py:15-72`

**Fields:**
- `bookmaster` (FK to BookMaster)
- `entity_type` (CharField) - From EntityType choices:
  - CHARACTER: "Character"
  - PLACE: "Place"
  - TERM: "Term"
- `source_name` (CharField) - Original entity name
- `translations` (JSONField) - {language_code: translated_name}
- `first_chapter` (FK to Chapter)
- `last_chapter` (FK to Chapter) - nullable
- `occurrence_count` (PositiveIntegerField)

**Constraints:**
- Unique together: [bookmaster, source_name]

### BookKeyword Model (Search Index)
Located: `/home/user/code/webnovel_claude/myapp/books/models/taxonomy.py:304-352`

**Fields:**
- `bookmaster` (FK to BookMaster)
- `keyword` (CharField) - Searchable text
- `keyword_type` (CharField) - From KeywordType choices:
  - SECTION, GENRE, TAG, ENTITY_CHARACTER, ENTITY_PLACE, ENTITY_TERM, TITLE, AUTHOR
- `language_code` (CharField)
- `weight` (FloatField) - Relevance weight for ranking

**Auto-Generated From:**
- Section names (weight: 1.5)
- Genre names (weight: 1.0)
- Tag names (weight: 0.8)
- Entity names (weight: 0.6)

---

## 5. EXISTING MODAL IMPLEMENTATION

### Location
Book card modal: lines 55-158 of `/home/user/code/webnovel_claude/myapp/reader/templates/reader/partials/book_card.html`

### Implementation Details

**HTML Structure:**
```html
<div class="modal fade" id="bookModal{{ book.id }}" tabindex="-1" 
     aria-labelledby="bookModalLabel{{ book.id }}" aria-hidden="true">
    <div class="modal-dialog modal-lg">
        <div class="modal-content">
            <!-- Header -->
            <div class="modal-header">...</div>
            <!-- Body -->
            <div class="modal-body">
                <div class="row">
                    <!-- Left: col-md-4 -->
                    <!-- Right: col-md-8 -->
                </div>
            </div>
            <!-- Footer -->
            <div class="modal-footer">...</div>
        </div>
    </div>
</div>
```

**Trigger Mechanism (line 25):**
```html
<button class="book-card-info-btn" 
        data-bs-toggle="modal" 
        data-bs-target="#bookModal{{ book.id }}" 
        onclick="event.preventDefault(); event.stopPropagation();">
    <i class="fas fa-info"></i>
</button>
```

**Modal Dialog:**
- Class: `modal fade` - Bootstrap fade animation
- Size: `modal-lg` - Large modal

**Modal Body Layout:**
- **Left Column (col-md-4):**
  - Book cover (img-fluid)
  - Section badge
  - All genres badges

- **Right Column (col-md-8):**
  - Book title (h4.fw-bold)
  - Author info with link
  - Description (stripped of HTML tags)
  - Stats grid:
    - Chapters, Status, Views (in col-6 layout)
    - Icons + labels + values

**Footer:**
- Close button (btn-outline-primary-custom)
- Read Now button (btn-primary-custom) - Links to book detail

---

## 6. HOW VIEWS PASS CONTEXT TO TEMPLATES

### Base View Classes
Located: `/home/user/code/webnovel_claude/myapp/reader/views/base.py`

**BaseReaderView.get_context_data() (lines 167-211):**
Adds universal context:
```python
context = {
    "current_language": Language object,
    "languages": List of accessible languages (cached),
    "sections": List of all sections with localized names (cached),
    "genres_hierarchical": Hierarchical genre structure by section (cached),
    "genres": Flat genre list (cached),
    "tags_by_category": Tags grouped by category (cached)
}
```

**BaseBookDetailView.get_context_data() (lines 405-448):**
Adds book-specific context:
```python
context = {
    "section_localized_name": Translated section name,
    "section": Section object,
    "genres": All genres with localized names and parent hierarchy,
    "tags_by_category": Tags grouped by category with localized names
}
```

**BookDetailView.get_context_data() (lines 48-92):**
Adds detail page context:
```python
context = {
    "author": Author object (if exists),
    "author_localized_name": Author's name in current language,
    "chapters": Paginated chapter queryset (20 per page),
    "is_paginated": Boolean,
    "page_obj": Paginator object,
    "total_chapters": Count of all published chapters,
    "total_words": Sum of all chapter words,
    "last_update": DateTime of most recent chapter,
    "total_chapter_views": Cached view count,
    "view_event_id": Created ViewEvent ID
}
```

**Enrichment Helper Method (lines 229-267):**
```python
def enrich_books_with_metadata(self, books, language_code):
    For each book, adds:
    - published_chapters_count (cached)
    - total_chapter_views (cached)
    - section_localized_name
    - For each genre:
        - localized_name
        - parent_localized_name (if has parent)
        - section_localized_name
```

### QuerySets with Optimization

**BookDetailView.get_queryset() (lines 32-46):**
```python
Book.objects.filter(language=language, is_public=True)
    .select_related(
        "bookmaster", 
        "bookmaster__section", 
        "bookmaster__author", 
        "language"
    )
    .prefetch_related(
        "chapters__chaptermaster",
        "bookmaster__genres",
        "bookmaster__genres__parent",
        "bookmaster__genres__section",
        "bookmaster__tags"
    )
```

---

## 7. KEY FINDINGS & INSIGHTS

### Taxonomy Structure
- **Hierarchical**: Sections contain Genres (primary and sub-genres)
- **Multi-language**: All taxonomy entities support localization via JSON translations
- **Controlled**: Genre hierarchy enforced with validation rules
- **Flexible**: Tags provide fine-grained metadata, optionally AI-suggested

### Template Context Flow
1. Views pass localized taxonomy to templates
2. Templates use `localized_name` properties (added by views)
3. Badge styling varies by taxonomy type:
   - Sections: bg-primary-custom (orange)
   - Genres: bg-secondary (gray)
   - Tags: bg-light with border (light gray)

### Caching Strategy
- Chapter counts cached per book
- Total views cached per book
- Languages, sections, genres cached globally
- Tags grouped by category cached globally

### Display Patterns
- **Book Cards**: Limited (up to 2 genres), section only
- **Book Detail**: All content displayed (all genres, all tags)
- **Modal**: Middle ground - all genres, section, but limited stats

### Modal Integration
- Used for quick preview from book card
- Unique ID per book prevents conflicts
- Bootstrap modal with fade animation
- Event prevention on trigger button

