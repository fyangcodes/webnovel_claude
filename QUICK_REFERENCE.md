# Quick Reference Guide - File Locations & Key Code

## Critical File Locations

### Templates
- **Book Card Partial**: `/home/user/code/webnovel_claude/myapp/reader/templates/reader/partials/book_card.html` (159 lines)
- **Book Detail**: `/home/user/code/webnovel_claude/myapp/reader/templates/reader/book_detail.html` (223 lines)
- **Author Detail**: `/home/user/code/webnovel_claude/myapp/reader/templates/reader/author_detail.html`
- **Base Template**: `/home/user/code/webnovel_claude/myapp/reader/templates/reader/base.html`

### Models
- **Core Models**: `/home/user/code/webnovel_claude/myapp/books/models/core.py` (454 lines)
  - Language (lines 24-59)
  - BookMaster (lines 61-208)
  - Book (lines 210-309)
  - ChapterMaster (lines 311-334)
  - Chapter (lines 336-454)

- **Taxonomy Models**: `/home/user/code/webnovel_claude/myapp/books/models/taxonomy.py` (393 lines)
  - Section (lines 23-65)
  - Genre (lines 67-176)
  - BookGenre (lines 178-219)
  - Tag (lines 221-263)
  - BookTag (lines 265-302)
  - BookKeyword (lines 304-352)
  - Author (lines 354-393)

- **Context Models**: `/home/user/code/webnovel_claude/myapp/books/models/context.py` (164 lines)
  - BookEntity (lines 15-72)
  - ChapterContext (lines 74-164)

- **Base Models**: `/home/user/code/webnovel_claude/myapp/books/models/base.py` (92 lines)
  - TimeStampModel (lines 33-43)
  - LocalizationModel (lines 46-92)
  - SlugGeneratorMixin (lines 8-30)

- **Choices**: `/home/user/code/webnovel_claude/myapp/books/choices.py` (70 lines)

### Views
- **Detail Views**: `/home/user/code/webnovel_claude/myapp/reader/views/detail_views.py` (227 lines)
  - BookDetailView (lines 18-92)
  - ChapterDetailView (lines 95-161)
  - AuthorDetailView (lines 163-227)

- **Base Views**: `/home/user/code/webnovel_claude/myapp/reader/views/base.py` (449 lines)
  - BaseReaderView (lines 20-211)
  - BaseBookListView (lines 214-279)
  - BaseSearchView (lines 282-388)
  - BaseBookDetailView (lines 390-449)

### CSS
- **Main Styles**: `/home/user/code/webnovel_claude/myapp/reader/static/reader/css/styles.css`
  - Color variables (lines 8-69)
  - Modal styles (lines 286-333)
  - Button styles (lines 222-260)
  - Badge info in Bootstrap classes

---

## Key Code Snippets

### How to Access Book Taxonomy in Templates

**Book Card (book_card.html, lines 32-41):**
```django
{% if book.section_localized_name %}
    <span class="badge bg-primary-custom">{{ book.section_localized_name }}</span>
{% endif %}

{% with book.bookmaster.genres.all|slice:":2" as genres %}
    {% for genre in genres %}
        <span class="badge bg-secondary">{{ genre.localized_name }}</span>
    {% endfor %}
{% endwith %}
```

**Book Detail (book_detail.html, lines 86-112):**
```django
{% for genre in genres %}
<a href="{% url 'reader:section_genre_book_list' current_language.code book.bookmaster.section.slug genre.slug %}"
   class="badge bg-secondary text-decoration-none">
    {% if genre.parent_localized_name %}
        {{ genre.parent_localized_name }} &rsaquo;
    {% endif %}
    {{ genre.localized_name }}
</a>
{% endfor %}
```

**Tags (book_detail.html, lines 116-142):**
```django
{% for category, tags in tags_by_category.items %}
    <div class="mb-2">
        <small class="text-muted d-block mb-1">{{ category }}</small>
        {% for tag in tags %}
            <a href="..." class="badge bg-light text-dark border">
                {{ tag.localized_name }}
            </a>
        {% endfor %}
    </div>
{% endfor %}
```

### Model Relationships in Python

**Accessing from Book instance:**
```python
book = Book.objects.get(id=1)

# Navigate to taxonomy
section = book.bookmaster.section
genres = book.bookmaster.genres.all()  # Through BookGenre
tags = book.bookmaster.tags.all()      # Through BookTag
author = book.bookmaster.author
entities = book.bookmaster.entities.all()

# Access with ordering (BookGenre has order field)
ordered_genres = book.bookmaster.book_genres.all().order_by('order')
for bg in ordered_genres:
    print(bg.genre.name, bg.order)
```

**Accessing from Section instance:**
```python
section = Section.objects.get(slug='fiction')

# Get all books in section
books = section.bookmasters.all()

# Get all genres in section
genres = section.genres.all()

# Get only primary genres
primary_genres = section.genres.filter(is_primary=True)
```

**Accessing from Genre instance:**
```python
genre = Genre.objects.get(slug='fantasy')

# Get parent (if sub-genre)
parent = genre.parent

# Get sub-genres (if primary)
sub_genres = genre.sub_genres.all()

# Get all books with this genre
books = genre.bookmasters.all()  # Through BookGenre
```

### View Context Building

**From BookDetailView (detail_views.py, lines 48-92):**
```python
def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)  # Calls BaseBookDetailView
    
    # Add author
    author = self.object.bookmaster.author
    if author:
        context["author"] = author
        context["author_localized_name"] = author.get_localized_name(language_code)
    
    # Add paginated chapters
    all_chapters = self.object.chapters.filter(is_public=True).select_related("chaptermaster")
    paginator = Paginator(all_chapters, 20)
    page_obj = paginator.get_page(self.request.GET.get("page"))
    
    context["chapters"] = page_obj
    context["total_chapters"] = all_chapters.count()
    
    return context
```

**From BaseBookDetailView (base.py, lines 405-448):**
```python
def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)  # Calls BaseReaderView
    
    # Localize genres with hierarchy
    genres = self.object.bookmaster.genres.all()
    for genre in genres:
        genre.localized_name = genre.get_localized_name(language_code)
        if genre.parent:
            genre.parent_localized_name = genre.parent.get_localized_name(language_code)
    context["genres"] = genres
    
    # Group tags by category
    tags = self.object.bookmaster.tags.all()
    tags_by_category = {}
    for tag in tags:
        tag.localized_name = tag.get_localized_name(language_code)
        category = tag.category
        if category not in tags_by_category:
            tags_by_category[category] = []
        tags_by_category[category].append(tag)
    context["tags_by_category"] = tags_by_category
    
    return context
```

**From BaseReaderView (base.py, lines 167-211):**
```python
def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    
    language_code = self.kwargs.get("language_code")
    
    # Add localized taxonomy
    context["current_language"] = self.get_language()
    context["languages"] = cache.get_cached_languages(user=self.request.user)
    
    sections = cache.get_cached_sections(user=self.request.user)
    context["sections"] = self.get_localized_sections(sections, language_code)
    
    genres_hierarchical = cache.get_cached_genres()
    context["genres_hierarchical"] = self.localize_hierarchical_genres(genres_hierarchical, language_code)
    
    tags_by_category = cache.get_cached_tags()
    for category, tags in tags_by_category.items():
        for tag in tags:
            tag.localized_name = tag.get_localized_name(language_code)
    context["tags_by_category"] = tags_by_category
    
    return context
```

### Localization Pattern

**In Model (all LocalizationModel subclasses):**
```python
class Genre(TimeStampModel, LocalizationModel):
    name = models.CharField(max_length=50)  # Default name
    translations = models.JSONField(default=dict)  # {"en": {"name": "..."}, "zh": {"name": "..."}}
    
    def get_localized_name(self, language_code):
        """Get localized name or fall back to default"""
        if language_code in self.translations:
            return self.translations[language_code].get('name', self.name)
        return self.name
```

**In Template:**
```django
{# Views set localized_name on model instances #}
{{ genre.localized_name }}  {# Already includes fallback logic #}

{# For direct access without view processing: #}
{{ section.get_localized_name current_language.code }}
```

### Modal Implementation Details

**Trigger (book_card.html, line 25):**
```html
<button class="book-card-info-btn" 
        data-bs-toggle="modal" 
        data-bs-target="#bookModal{{ book.id }}"
        onclick="event.preventDefault(); event.stopPropagation();">
    <i class="fas fa-info"></i>
</button>
```

**Modal HTML (book_card.html, lines 55-158):**
```html
<div class="modal fade" id="bookModal{{ book.id }}" tabindex="-1">
    <div class="modal-dialog modal-lg">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title">Book Details</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
            </div>
            <div class="modal-body">
                <div class="row">
                    {# Left: Book cover + section + genres #}
                    {# Right: Title + author + description + stats #}
                </div>
            </div>
            <div class="modal-footer">
                <button type="button" class="btn btn-outline-primary-custom" data-bs-dismiss="modal">Close</button>
                <a href="..." class="btn btn-primary-custom">Read Now</a>
            </div>
        </div>
    </div>
</div>
```

---

## Display Patterns Summary

### Book Card
- Shows: section (1), genres (up to 2), stats
- Modal shows: all genres with hierarchy, section, stats
- Grid layout (12 per page typical)

### Book Detail
- Shows: section, all genres with hierarchy, all tags grouped by category
- Two-column layout (content + sidebar)
- 20 chapters per page
- Full chapter list with pagination

### Author Detail
- Shows: author info, author's books as cards
- Each book card same as regular book card
- Uses same enrichment logic

---

## CSS Classes to Know

**Badges:**
- `bg-primary-custom` - Orange (sections)
- `bg-secondary` - Gray (genres)
- `bg-light text-dark border` - Light gray (tags)
- `badge` - Bootstrap badge base class

**Layout:**
- `col-lg-8`, `col-lg-4` - Main content + sidebar
- `col-md-4`, `col-md-8` - Modal left/right
- `d-flex`, `gap-2` - Flex layout with gap
- `flex-wrap` - Wrap to next line

**Typography:**
- `.fw-bold`, `.fw-medium` - Font weight
- `.text-muted`, `.text-light`, `.text-dark` - Text colors
- `.small`, `.muted` - Size and style

**Modals:**
- `.modal.fade` - Modal with fade animation
- `.modal-lg` - Large modal
- `.modal-header`, `.modal-body`, `.modal-footer` - Sections

---

## Important Notes

1. **Localized Names**: Views add `localized_name` property to taxonomy objects
2. **Caching**: Global taxonomy is cached; per-book data is cached per request
3. **Hierarchy**: Genres have parent-child relationships (primary/sub-genres)
4. **Sections**: Top-level organization; genres belong to sections
5. **Tags**: Flexible metadata, grouped by category in display
6. **Entities**: Characters, places, terms extracted from chapters
7. **Through Models**: BookGenre and BookTag provide metadata (order, confidence)

