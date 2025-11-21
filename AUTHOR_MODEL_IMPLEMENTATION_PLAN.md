# Author Model Implementation Plan

## ⚠️ IMPORTANT NOTE

**This plan has been superseded by the [TAXONOMY_REFACTORING_PLAN.md](TAXONOMY_REFACTORING_PLAN.md).**

The new approach uses a `LocalizedTaxonomyMixin` abstract base model that provides shared fields and methods for Section, Genre, Tag, and Author models. This follows the DRY principle and ensures better code maintainability.

**Please refer to TAXONOMY_REFACTORING_PLAN.md for the recommended implementation.**

---

## Overview (Original Plan)

This document outlines the original implementation plan for adding a language-independent Author model to the taxonomy system. The Author model will follow the same pattern as Genre and Tag models with translations support.

## Objectives

- Create a language-independent Author entity at the BookMaster level
- Support multi-language author names and biographies
- Integrate with existing taxonomy and search systems
- Maintain consistency with existing model patterns

## Why This Plan Was Superseded

After analyzing the shared patterns across Section, Genre, Tag, and Author models, we identified significant code duplication:
- All models share: `name`, `slug`, `description`, `translations` fields
- All models share: `get_localized_name()`, `get_localized_description()` methods
- All models share: Auto-slug generation logic in `save()`

The refactoring plan creates a `LocalizedTaxonomyMixin` that eliminates this duplication while maintaining the same functionality.

## Implementation Steps

### 1. Model Definition

**File**: `myapp/books/models/taxonomy.py`
**Location**: After the `Section` model (around line 88)

Add a new `Author` model:

```python
class Author(TimeStampedModel):
    """
    Language-independent author entity.

    Authors are shared across all language versions of books.
    Translators are stored in the Book model (language-specific).
    """

    name = models.CharField(
        max_length=100,
        unique=True,
        help_text="Author's canonical name"
    )
    slug = models.SlugField(
        max_length=100,
        unique=True,
        help_text="URL-friendly identifier"
    )
    description = models.TextField(
        blank=True,
        help_text="Author biography or description"
    )
    avatar = models.ImageField(
        upload_to="authors/",
        blank=True,
        null=True,
        help_text="Author profile image"
    )
    translations = models.JSONField(
        default=dict,
        blank=True,
        help_text="Localized names and descriptions. Format: {language_code: {name, description}}"
    )

    class Meta:
        ordering = ['name']
        verbose_name = "Author"
        verbose_name_plural = "Taxonomy - Authors"
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['name']),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_localized_name(self, language_code):
        """Get localized author name or fall back to default"""
        if language_code in self.translations:
            return self.translations[language_code].get('name', self.name)
        return self.name

    def get_localized_description(self, language_code):
        """Get localized author description or fall back to default"""
        if language_code in self.translations:
            return self.translations[language_code].get('description', self.description)
        return self.description
```

### 2. Update BookMaster Relationship

**File**: `myapp/books/models/core.py`
**Location**: Around line 133, after the `tags` field

Add an `author` foreign key to the `BookMaster` model:

```python
author = models.ForeignKey(
    'Author',
    on_delete=models.SET_NULL,
    null=True,
    blank=True,
    related_name='bookmasters',
    help_text="Original author of the work"
)
```

### 3. Update Model Exports

**File**: `myapp/books/models/__init__.py`

**A. Import Author** (line 22):
```python
from .taxonomy import (
    Section,
    Genre,
    BookGenre,
    Tag,
    BookTag,
    BookKeyword,
    Author,  # Add this
)
```

**B. Add to __all__** (around line 61):
```python
__all__ = [
    # ... existing exports
    "Author",  # Add after BookKeyword
]
```

### 4. Admin Configuration

**File**: `myapp/books/admin.py`

#### A. Import the Model (line 12)

```python
from .models import (
    # Core
    Language,
    BookMaster,
    Book,
    ChapterMaster,
    Chapter,
    # Taxonomy
    Section,
    Author,  # Add this after Section
    Genre,
    # ... rest of imports
)
```

#### B. Create AuthorAdmin Class (after SectionAdmin, around line 220)

```python
@admin.register(Author)
class AuthorAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "created_at"]
    search_fields = ["name", "slug"]
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ["pk", "created_at", "updated_at"]
    ordering = ["name"]

    fieldsets = (
        (None, {
            "fields": ("pk", "name", "slug", "description", "avatar")
        }),
        (
            "Translations",
            {
                "fields": ("translations",),
                "description": 'JSON field for localized names and descriptions. Format: {"zh": {"name": "天蚕土豆", "description": "..."}, "en": {...}}',
                "classes": ("collapse",),
            },
        ),
        (
            "Timestamps",
            {
                "fields": ("created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )
```

#### C. Update BookMasterAdmin

**1. Add to fieldsets** (around line 410):
```python
fieldsets = (
    (None, {
        "fields": ("pk", "canonical_title", "author", "section", "owner", "original_language")
        #                                     ^^^^^^ Add this
    }),
    # ... rest of fieldsets
)
```

**2. Add to list_display** (around line 395):
```python
list_display = [
    "canonical_title",
    "author",  # Add this
    "section",
    "owner",
    "original_language",
    "genre_list",
    "tag_list",
    "created_at",
]
```

**3. Add to list_filter** (around line 403):
```python
list_filter = ["section", "author", "original_language", "created_at"]
#                         ^^^^^^^^ Add this
```

### 5. Update BookKeyword Integration (Optional)

To make authors searchable via the keyword system:

**File**: `myapp/books/choices.py`

Add author keyword type:

```python
class KeywordType(models.TextChoices):
    SECTION = 'section', 'Section'
    GENRE = 'genre', 'Genre'
    TAG = 'tag', 'Tag'
    AUTHOR = 'author', 'Author'  # Add this
    ENTITY_CHARACTER = 'entity_character', 'Character'
    ENTITY_PLACE = 'entity_place', 'Place'
    ENTITY_TERM = 'entity_term', 'Term'
```

**File**: `myapp/books/utils/search.py` (or relevant search utility)

Add author keyword generation logic to index authors in the search system.

### 6. Database Migration

Run the following commands to create and apply migrations:

```bash
cd myapp
python manage.py makemigrations books -n "add_author_model"
python manage.py migrate books
```

### 7. Update Seed Data (Optional)

**File**: `myapp/books/management/commands/seed_taxonomy.py`

Add a function to create sample authors:

```python
def create_authors():
    """Create sample authors"""
    authors_data = [
        {
            'name': 'Tian Can Tu Dou (天蚕土豆)',
            'description': 'Popular Chinese web novel author known for Battle Through the Heavens',
            'translations': {
                'zh': {
                    'name': '天蚕土豆',
                    'description': '著名网络小说作家，代表作《斗破苍穹》'
                },
                'en': {
                    'name': 'Tian Can Tu Dou (Heavenly Silkworm Potato)',
                    'description': 'Popular Chinese web novel author known for Battle Through the Heavens'
                }
            }
        },
        {
            'name': 'Er Gen (耳根)',
            'description': 'Acclaimed Chinese web novel author known for I Shall Seal the Heavens',
            'translations': {
                'zh': {
                    'name': '耳根',
                    'description': '著名网络小说作家，代表作《我欲封天》'
                },
                'en': {
                    'name': 'Er Gen',
                    'description': 'Acclaimed Chinese web novel author known for I Shall Seal the Heavens'
                }
            }
        },
        {
            'name': 'I Eat Tomatoes (我吃西红柿)',
            'description': 'Prolific Chinese web novel author known for Coiling Dragon',
            'translations': {
                'zh': {
                    'name': '我吃西红柿',
                    'description': '著名网络小说作家，代表作《盘龙》'
                },
                'en': {
                    'name': 'I Eat Tomatoes',
                    'description': 'Prolific Chinese web novel author known for Coiling Dragon'
                }
            }
        },
    ]

    authors = []
    for data in authors_data:
        author, created = Author.objects.get_or_create(
            name=data['name'],
            defaults={
                'description': data['description'],
                'translations': data['translations']
            }
        )
        authors.append(author)
        if created:
            self.stdout.write(f"  Created author: {author.name}")

    return authors
```

Update the `handle` method to call `create_authors()`:

```python
def handle(self, *args, **options):
    # ... existing code
    authors = create_authors()
    # ... rest of code
```

### 8. Update Documentation

**File**: `CLAUDE.md`

Add Author model documentation in the "Hierarchical Taxonomy System" section:

```markdown
#### Author (`books.models.Author`)

Language-independent author entity.

**Fields**:
- `name`: Author's canonical name (unique)
- `slug`: URL-friendly identifier
- `description`: Author biography
- `avatar`: Author profile image
- `translations`: JSON field for localized names and descriptions

**Relationships**:
- `bookmasters`: Reverse relation to BookMaster (books by this author)

**Usage**:
```python
from books.models import Author

# Get author
author = Author.objects.get(slug='tian-can-tu-dou')
print(author.get_localized_name('zh'))  # "天蚕土豆"

# Get all books by author
books = author.bookmasters.all()
```
```

## Key Design Decisions

### 1. Language-Independent Model
- Authors are stored at the `BookMaster` level, not `Book` level
- Represents the original creator of the work
- Shared across all language versions of a book

### 2. Translator vs Author Distinction
- `BookMaster.author`: Original author (language-independent)
- `Book.author` field: Can be repurposed for translator names (language-specific)
- Clear separation of concerns

### 3. Consistent Pattern
- Follows same pattern as `Genre` and `Tag` models
- Uses `translations` JSON field for multi-language support
- Includes localization helper methods

### 4. Search Integration
- Can optionally be integrated into the keyword search system
- Adds `AUTHOR` keyword type
- Enables author-based search and filtering

### 5. Unique Constraint
- Author names are globally unique
- Prevents duplicate author entries
- Single source of truth for each author

### 6. Avatar Support
- Optional profile image for authors
- Stored in `media/authors/` directory
- Enables rich author profile pages

## Migration Strategy

### Safe Migration
- Using `SET_NULL` on foreign key ensures existing data isn't affected
- No data loss during migration
- Can be rolled back if needed

### Backwards Compatible
- All fields are optional/nullable initially
- Doesn't modify existing models, only adds new ones
- Existing functionality remains unchanged

### No Breaking Changes
- Additive changes only
- No removal of existing fields
- API remains stable

## Benefits

1. **Multi-language Support**: Author names displayed in user's preferred language
2. **Centralized Management**: One author entity shared across all translations
3. **SEO Friendly**: Slugs enable author profile pages (`/authors/tian-can-tu-dou/`)
4. **Avatar Support**: Rich author profiles with images
5. **Searchable**: Integration with keyword search system
6. **Consistent Architecture**: Follows established taxonomy patterns
7. **Scalable**: Supports unlimited authors and translations

## Future Enhancements

### Phase 2 (Optional)
- Author profile pages in reader app
- "Books by this author" browsing
- Author statistics (total books, total views, etc.)
- Social media links field
- Author verification/badge system

### Phase 3 (Optional)
- Multiple authors per book (many-to-many relationship)
- Co-author support
- Author pseudonyms/pen names management
- Author following/subscription system

## Testing Checklist

After implementation, verify:

- [ ] Model can be created via Django admin
- [ ] Slug auto-generation works correctly
- [ ] Translations are stored and retrieved properly
- [ ] BookMaster can be assigned an author
- [ ] Author appears in BookMaster admin list view
- [ ] Author filtering works in admin
- [ ] Search functionality includes authors (if keyword integration done)
- [ ] Migration runs without errors
- [ ] No existing data is affected
- [ ] Avatar upload works correctly

## Timeline Estimate

- Model creation and relationships: 30 minutes
- Admin configuration: 20 minutes
- Keyword integration (optional): 30 minutes
- Migration and testing: 15 minutes
- Seed data creation: 15 minutes
- Documentation updates: 10 minutes

**Total**: ~2 hours (including optional features and testing)

## Dependencies

- No external dependencies required
- Uses existing Django features
- Compatible with current codebase architecture

## Rollback Plan

If issues arise:

1. Revert migration: `python manage.py migrate books <previous_migration>`
2. Remove Author imports from code
3. Restore previous version of files
4. No data loss since foreign key uses `SET_NULL`

## References

- Genre model: `myapp/books/models/taxonomy.py:89-216`
- Tag model: `myapp/books/models/taxonomy.py:261-326`
- BookMaster model: `myapp/books/models/core.py:82-221`
- Admin patterns: `myapp/books/admin.py`
