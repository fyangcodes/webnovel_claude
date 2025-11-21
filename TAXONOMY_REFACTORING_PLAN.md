# Taxonomy Models Refactoring Plan

## Overview

Refactor Section, Genre, Tag, and Author models to inherit from a shared abstract base model that provides common fields and methods. This follows the DRY (Don't Repeat Yourself) principle and ensures consistency across taxonomy models.

## Shared Patterns Analysis

### Common Fields
All taxonomy models share:
- `name`: CharField (varying max_length)
- `slug`: SlugField (unique or unique_together constraints)
- `description`: TextField (blank=True)
- `translations`: JSONField (default=dict, same format)

### Common Methods
All models implement:
- `get_localized_name(language_code)`: Returns localized name or fallback
- `get_localized_description(language_code)`: Returns localized description or fallback
- `save()`: Auto-generates slug from name if not provided

### Differences to Preserve
- **Section**: Has `order`, `is_mature` fields
- **Genre**: Has `section` FK, `parent` FK, `is_primary`, complex validation
- **Tag**: Has `category` field with choices
- **Author**: Has `avatar` field

## Proposed Solution

### 1. Create LocalizationModel

**File**: `myapp/books/models/base.py`

Add a new abstract base model that provides localization infrastructure:

```python
class LocalizationModel(models.Model):
    """
    Abstract base model for taxonomy entities with localization support.

    Provides common fields and methods for taxonomy models like Section,
    Genre, Tag, and Author that need multi-language support.
    """

    name = models.CharField(
        max_length=100,
        help_text="Canonical name (default language)"
    )
    slug = models.SlugField(
        max_length=100,
        help_text="URL-friendly identifier"
    )
    description = models.TextField(
        blank=True,
        help_text="Description or details"
    )
    translations = models.JSONField(
        default=dict,
        blank=True,
        help_text="Localized names and descriptions. Format: {language_code: {name, description}}"
    )

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        """Auto-generate slug from name if not provided"""
        if not self.slug:
            from django.utils.text import slugify
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_localized_name(self, language_code):
        """Get localized name or fall back to default"""
        if language_code in self.translations:
            return self.translations[language_code].get('name', self.name)
        return self.name

    def get_localized_description(self, language_code):
        """Get localized description or fall back to default"""
        if language_code in self.translations:
            return self.translations[language_code].get('description', self.description)
        return self.description
```

### 2. Update Individual Models

Each model will inherit from both `TimeStampModel` and `LocalizationModel`, then add model-specific fields and logic.

#### Section Model (Simplified)

```python
class Section(TimeStampModel, LocalizationModel):
    """
    Top-level content category for books.

    Sections represent fundamentally different content types that may require
    different moderation, age-gating, or browsing experiences.
    Examples: Fiction, BL (Boys' Love), GL (Girls' Love), Non-fiction
    """

    # Override name to make it unique
    name = models.CharField(
        max_length=50,
        unique=True,
        help_text="Section name (e.g., 'Fiction', 'BL', 'GL')"
    )
    slug = models.SlugField(
        max_length=50,
        unique=True,
        help_text="URL-friendly identifier"
    )

    # Section-specific fields
    order = models.PositiveSmallIntegerField(
        default=0,
        help_text="Display order (lower = first)"
    )
    is_mature = models.BooleanField(
        default=False,
        help_text="Whether this section contains mature content requiring age verification"
    )

    class Meta:
        ordering = ['order', 'name']
        verbose_name = "Section"
        verbose_name_plural = "Taxonomy - Sections"
        indexes = [
            models.Index(fields=['order']),
            models.Index(fields=['slug']),
        ]

    def __str__(self):
        return self.name
```

#### Genre Model (Simplified)

```python
class Genre(TimeStampModel, LocalizationModel):
    """
    Hierarchical genre classification system.

    Genres are organized within sections and can be:
    - Primary genres (is_primary=True, parent=None): Main categories for browsing
    - Sub-genres (is_primary=False, parent=<primary>): Refinements of primary genres

    Note: Genre names can repeat across sections (e.g., "Romance" in both Fiction and BL),
    enforced by unique_together on (section, slug).
    """

    # Genre-specific fields
    section = models.ForeignKey(
        Section,
        on_delete=models.CASCADE,
        related_name='genres',
        null=True,
        blank=True,
        help_text="The section this genre belongs to"
    )
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='sub_genres',
        help_text="Parent genre (only for sub-genres)"
    )
    is_primary = models.BooleanField(
        default=True,
        help_text="Primary genres appear in main navigation; sub-genres are refinements"
    )

    class Meta:
        ordering = ['section', '-is_primary', 'name']
        verbose_name = "Genre"
        verbose_name_plural = "Taxonomy - Genres"
        unique_together = [['section', 'slug']]
        indexes = [
            models.Index(fields=['section', 'is_primary']),
            models.Index(fields=['section', 'slug']),
            models.Index(fields=['parent']),
        ]

    def __str__(self):
        if not self.section:
            return self.name
        if self.parent:
            return f"{self.section.name} > {self.parent.name} > {self.name}"
        return f"{self.section.name} > {self.name}"

    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify
            self.slug = slugify(self.name)
        # Call clean() to validate before saving
        self.full_clean()
        super().save(*args, **kwargs)

    def clean(self):
        """Validate genre hierarchy rules"""
        from django.core.exceptions import ValidationError
        super().clean()

        # Rule 1: Primary genres cannot have parents
        if self.is_primary and self.parent:
            raise ValidationError({
                'parent': "Primary genres cannot have a parent genre. Set is_primary=False for sub-genres."
            })

        # Rule 2: Sub-genres must have a primary parent
        if not self.is_primary:
            if not self.parent:
                raise ValidationError({
                    'parent': "Sub-genres must have a parent genre."
                })
            if not self.parent.is_primary:
                raise ValidationError({
                    'parent': "Sub-genres must have a primary genre as parent (no nested sub-genres)."
                })

        # Rule 3: Parent must be in the same section
        if self.parent and self.section and self.parent.section != self.section:
            raise ValidationError({
                'parent': f"Parent genre must belong to the same section ({self.section.name})."
            })

        # Rule 4: Self-reference check (genre cannot be its own parent)
        if self.parent and self.pk and self.parent.pk == self.pk:
            raise ValidationError({
                'parent': "A genre cannot be its own parent."
            })

        # Rule 5: Circular reference check (prevent A -> B -> A)
        if self.parent and self.parent.parent and self.pk:
            if self.parent.parent.pk == self.pk:
                raise ValidationError({
                    'parent': f"Circular reference detected: {self.name} -> {self.parent.name} -> "
                              f"{self.parent.parent.name} creates a loop back to {self.name}."
                })
```

#### Tag Model (Simplified)

```python
class Tag(TimeStampModel, LocalizationModel):
    """
    Flexible tagging system for book attributes.

    Tags provide fine-grained metadata about books, such as:
    - Protagonist type (female-lead, male-lead)
    - Narrative style (first-person, third-person)
    - Themes (revenge, redemption)
    - Tropes (system, transmigration, regression)
    - Content warnings (violence, sexual content)
    """

    # Override name to make it unique
    name = models.CharField(
        max_length=50,
        unique=True,
        help_text="Tag name (e.g., 'Female Lead', 'System')"
    )
    slug = models.SlugField(
        max_length=50,
        unique=True,
        help_text="URL-friendly identifier"
    )

    # Tag-specific field
    category = models.CharField(
        max_length=20,
        choices=TagCategory.choices,
        help_text="Category for organizing tags"
    )

    class Meta:
        ordering = ['category', 'name']
        verbose_name = "Tag"
        verbose_name_plural = "Taxonomy - Tags"
        indexes = [
            models.Index(fields=['category']),
            models.Index(fields=['slug']),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_category_display()})"
```

#### Author Model (New)

```python
class Author(TimeStampModel, LocalizationModel):
    """
    Language-independent author entity.

    Authors are shared across all language versions of books.
    Translators are stored in the Book model (language-specific).
    """

    # Override name to make it unique
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

    # Author-specific field
    avatar = models.ImageField(
        upload_to="authors/",
        blank=True,
        null=True,
        help_text="Author profile image"
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
```

## Implementation Steps

### Step 0: Rename TimeStampedModel to TimeStampModel

**File**: `myapp/books/models/base.py`

Rename the existing `TimeStampedModel` class to `TimeStampModel` for consistent noun-based naming:

```python
# Before
class TimeStampedModel(models.Model):
    ...

# After
class TimeStampModel(models.Model):
    ...
```

**Files to update** (8 files total):
1. `myapp/books/models/base.py` - Class definition
2. `myapp/books/models/__init__.py` - Import and export
3. `myapp/books/models/core.py` - Import and inheritance
4. `myapp/books/models/taxonomy.py` - Import and inheritance
5. `myapp/books/models/job.py` - Import and inheritance
6. `myapp/books/models/context.py` - Import and inheritance
7. `myapp/books/models/stat.py` - Import and inheritance
8. `myapp/reader/models.py` - Import and inheritance

**Note**: This is a code-only change. Since it's an abstract model, no database migration is required.

### Step 1: Create LocalizationModel

**File**: `myapp/books/models/base.py`

1. Add the `LocalizationModel` class after `TimeStampModel`
2. Include all common fields and methods

### Step 2: Update Model Imports

**File**: `myapp/books/models/taxonomy.py`

Update imports:
```python
from books.models.base import TimeStampModel, LocalizationModel
```

### Step 3: Refactor Section Model

**File**: `myapp/books/models/taxonomy.py`

1. Add `LocalizationModel` to inheritance
2. Override `name` and `slug` fields with model-specific constraints
3. Remove `description`, `translations` fields (inherited)
4. Remove `get_localized_name()`, `get_localized_description()` methods (inherited)
5. Keep model-specific fields: `order`, `is_mature`
6. Keep/update `save()` if custom logic needed beyond slug generation

### Step 4: Refactor Genre Model

**File**: `myapp/books/models/taxonomy.py`

1. Add `LocalizationModel` to inheritance
2. Remove `name`, `slug`, `description`, `translations` fields (inherited)
3. Remove `get_localized_name()`, `get_localized_description()` methods (inherited)
4. Keep model-specific fields: `section`, `parent`, `is_primary`
5. Keep `save()` with custom validation logic
6. Keep all `clean()` validation methods

### Step 5: Refactor Tag Model

**File**: `myapp/books/models/taxonomy.py`

1. Add `LocalizationModel` to inheritance
2. Override `name` and `slug` fields with unique=True
3. Remove `description`, `translations` fields (inherited)
4. Remove `get_localized_name()`, `get_localized_description()` methods (inherited)
5. Keep model-specific field: `category`

### Step 6: Add Author Model

**File**: `myapp/books/models/taxonomy.py`

1. Create new `Author` class inheriting from `TimeStampModel` and `LocalizationModel`
2. Override `name` and `slug` fields with unique=True
3. Add model-specific field: `avatar`
4. No custom save() or clean() needed (uses inherited)

### Step 7: Update Model Exports

**File**: `myapp/books/models/__init__.py`

Update base model imports:
```python
from .base import TimeStampModel, LocalizationModel
```

Add to `__all__`:
```python
__all__ = [
    # Base
    "TimeStampModel",
    "LocalizationModel",
    # ... rest
    "Author",
]
```

### Step 8: Test - No Migration Needed

Since we're refactoring without changing the database schema:
- No migration required (fields remain the same)
- All existing data remains intact
- Only code structure changes

### Step 9: Update Documentation

**File**: `CLAUDE.md`

Add documentation about `LocalizationModel` in the architecture section.

## Key Benefits

### 1. DRY Principle
- Eliminates code duplication across 4 models
- Single source of truth for localization logic
- Reduces maintenance burden

### 2. Consistency
- All taxonomy models behave identically for localization
- Consistent method signatures across models
- Easier to understand and predict behavior

### 3. Maintainability
- Changes to localization logic only need to be made once
- Easier to add new features (e.g., `get_all_translations()`)
- Clearer model structure focusing on model-specific logic

### 4. Extensibility
- Easy to add new taxonomy models in the future
- Can add more shared methods to mixin as needed
- Supports composition over inheritance

### 5. Type Safety
- IDE autocomplete works better with shared interface
- Easier to write generic utility functions
- Better type hints for localization methods

## Considerations

### Field Override Pattern

When a model needs unique constraints or different parameters, override the field:

```python
class Tag(TimeStampModel, LocalizationModel):
    # Override to add unique=True
    name = models.CharField(
        max_length=50,
        unique=True,  # Add constraint
        help_text="Tag name (e.g., 'Female Lead', 'System')"
    )
```

### Method Override Pattern

If a model needs custom save logic, call super() to preserve mixin behavior:

```python
def save(self, *args, **kwargs):
    # Custom logic first
    self.custom_field = self.process_something()

    # Call parent to get slug generation
    super().save(*args, **kwargs)
```

### Multiple Inheritance Order

Always put `TimeStampModel` first, then `LocalizationModel`:
```python
class MyModel(TimeStampModel, LocalizationModel):
    pass
```

This ensures:
1. Timestamps are added first
2. Localization fields are added second
3. MRO (Method Resolution Order) is predictable

## Migration Strategy

### Phase 1: Add Mixin (No Migration)
- Create `LocalizationModel` in base.py
- Code change only, no database changes
- Safe to deploy

### Phase 2: Refactor Existing Models (No Migration)
- Update Section, Genre, Tag to inherit from mixin
- Remove duplicate code
- No database schema changes
- Safe to deploy

### Phase 3: Add Author Model (Requires Migration)
- Create Author model
- Add FK to BookMaster
- Run migration
- Deploy with migration

### Testing Strategy

After refactoring, verify:

1. **All localization methods work**:
   ```python
   section.get_localized_name('zh')
   genre.get_localized_description('en')
   ```

2. **Slug generation still works**:
   ```python
   tag = Tag(name="Female Lead")
   tag.save()
   assert tag.slug == "female-lead"
   ```

3. **Translations are stored correctly**:
   ```python
   author.translations = {'zh': {'name': '张三', 'description': '...'}}
   author.save()
   assert author.get_localized_name('zh') == '张三'
   ```

4. **Model-specific logic preserved**:
   - Genre validation rules still enforced
   - Section ordering works
   - Tag categories work

5. **Admin interface unchanged**:
   - All fields display correctly
   - Prepopulated slugs work
   - Translations collapse/expand works

## Alternative Approaches Considered

### Approach 1: Abstract Model (Chosen)
✅ **Pros**: Clean inheritance, no extra queries, standard Django pattern
❌ **Cons**: Can't query across all taxonomy types

### Approach 2: Concrete Base Model with Multi-Table Inheritance
❌ **Pros**: Can query all taxonomy types together
❌ **Cons**: Extra JOIN on every query, extra table, performance overhead

### Approach 3: Composition with Separate Model
❌ **Pros**: More flexible relationships
❌ **Cons**: FK overhead, more complex queries, breaks atomicity

**Decision**: Abstract model (Approach 1) is the best fit for this use case.

## Timeline Estimate

- Rename TimeStampedModel to TimeStampModel: 10 minutes
- Add LocalizationModel: 15 minutes
- Refactor Section: 10 minutes
- Refactor Genre: 15 minutes (preserve validation)
- Refactor Tag: 10 minutes
- Add Author model: 15 minutes
- Update admin: 10 minutes
- Testing: 20 minutes
- Documentation: 10 minutes

**Total**: ~2 hours

## Code Examples

### Using Localization in Views

```python
def book_detail(request, slug):
    book = Book.objects.get(slug=slug)
    language = request.user.preferred_language or 'en'

    # Get localized taxonomy names
    section_name = book.bookmaster.section.get_localized_name(language)
    genre_names = [
        genre.get_localized_name(language)
        for genre in book.bookmaster.genres.all()
    ]
    author_name = book.bookmaster.author.get_localized_name(language)

    return render(request, 'book_detail.html', {
        'book': book,
        'section_name': section_name,
        'genre_names': genre_names,
        'author_name': author_name,
    })
```

### Batch Translation Query

```python
def get_all_translations(taxonomy_item):
    """Get all available translations for a taxonomy item"""
    translations = {'default': {
        'name': taxonomy_item.name,
        'description': taxonomy_item.description,
    }}

    for lang_code, trans in taxonomy_item.translations.items():
        translations[lang_code] = trans

    return translations
```

### Generic Utility Function

```python
def localize_taxonomy_items(items, language_code):
    """Localize a list of taxonomy items (works for any model with mixin)"""
    return [
        {
            'name': item.get_localized_name(language_code),
            'description': item.get_localized_description(language_code),
            'slug': item.slug,
        }
        for item in items
    ]
```

## References

- Current models: `myapp/books/models/taxonomy.py`
- Base models: `myapp/books/models/base.py`
- Django abstract models: https://docs.djangoproject.com/en/stable/topics/db/models/#abstract-base-classes
