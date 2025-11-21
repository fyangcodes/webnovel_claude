# Section Navigation Styling Implementation Plan

## Overview

Create a `StyleConfig` model in the reader app to provide extensible styling capabilities for UI elements. Section and Genre models will reference StyleConfig via OneToOneField, maintaining clean separation between business logic (books app) and presentation logic (reader app).

## Design Philosophy

1. **Separation of Concerns**: Business logic (books) vs presentation (reader)
2. **Extensibility**: StyleConfig can easily grow with new fields
3. **Reusability**: One styling system for all UI elements
4. **Clean Architecture**: Presentation layer provides styling for data layer
5. **Simple but Extensible**: Start simple but designed for growth

## Architecture

```
books app (business logic)          reader app (presentation)
├── Section (100% independent!)      ├── StyleConfig (Generic)
├── Genre                            │   ├── content_type (FK)
└── BookMaster                       │   ├── object_id
    (NO reference to reader!)        │   ├── content_object (Generic)
                                     │   ├── color
                                     │   ├── icon
                                     │   └── custom_styles (JSON)
                                     │
                                     └── Helper Functions/Template Tags
                                         └── get_style_for_object(obj)

Access: {% get_style section %} (template tag in reader app)
```

**Key Benefits**:
- ✅ **100% Independence**: Books app has ZERO knowledge of reader app
- ✅ **No imports**: Books models don't import anything from reader
- ✅ **Works standalone**: Books app functions perfectly without reader
- ✅ **Universal styling**: Can style ANY model without code changes
- ✅ **True separation**: Presentation (reader) depends on business (books), never reverse

## Model Changes

### 1. Create StyleConfig Model

**File**: `/myapp/reader/models.py`

```python
from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from books.models.base import TimeStampedModel


class StyleConfig(TimeStampedModel):
    """
    Generic UI styling configuration for any model.

    Uses ContentType to style any model without tight coupling.
    Can be applied to Section, Genre, Tag, BookMaster, or any future model.

    Access from styled object: section.style (via GenericRelation)
    """

    # Generic relation to any model
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        help_text="Type of object this style applies to"
    )
    object_id = models.PositiveIntegerField(
        help_text="ID of the object this style applies to"
    )
    content_object = GenericForeignKey('content_type', 'object_id')

    # Color styling
    color = models.CharField(
        max_length=7,
        blank=True,
        default='',
        help_text="Primary color in hex format (e.g., '#FF5733')"
    )

    # Icon styling
    icon = models.CharField(
        max_length=50,
        blank=True,
        default='',
        help_text="FontAwesome icon class (e.g., 'fas fa-book')"
    )

    # Extensible styling via JSON
    custom_styles = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional CSS properties: {font_weight, border_radius, hover_color, etc.}"
    )

    class Meta:
        verbose_name = "Style Configuration"
        verbose_name_plural = "Style Configurations"
        # Ensure one style per object
        unique_together = [['content_type', 'object_id']]
        indexes = [
            models.Index(fields=['content_type', 'object_id']),
        ]

    def __str__(self):
        return f"Style for {self.content_object} (color: {self.color or 'default'})"

    def get_style_property(self, key, default=None):
        """Get a custom style property with fallback"""
        return self.custom_styles.get(key, default)

    def set_style_property(self, key, value):
        """Set a custom style property"""
        self.custom_styles[key] = value
```

### 2. Remove icon/color fields from Section Model

**File**: `/myapp/books/models/taxonomy.py`

**Simply remove the icon field**:
```python
class Section(TimeStampedModel):
    # ... existing fields ...
    icon = models.CharField(...)  # REMOVE THIS - moving to StyleConfig

    # NO GenericRelation
    # NO style field
    # NO imports from reader app
    # 100% independent!
```

**Note**: Section model remains completely independent.

### 3. Remove icon/color fields from Genre Model

**File**: `/myapp/books/models/taxonomy.py`

**Simply remove the icon and color fields**:
```python
class Genre(TimeStampedModel):
    # ... existing fields ...
    icon = models.CharField(...)  # REMOVE THIS
    color = models.CharField(...)  # REMOVE THIS

    # NO GenericRelation
    # NO style field
    # NO imports from reader app
    # 100% independent!
```

**Note**: Genre model remains completely independent.

### 4. Create Helper Functions in Reader App

**File**: `/myapp/reader/utils.py` (new file)

```python
"""Helper functions for accessing style configurations."""
from django.contrib.contenttypes.models import ContentType
from reader.models import StyleConfig


def get_style_for_object(obj):
    """
    Get StyleConfig for any object.

    Args:
        obj: Any Django model instance

    Returns:
        StyleConfig instance or None
    """
    if obj is None:
        return None

    try:
        content_type = ContentType.objects.get_for_model(obj.__class__)
        return StyleConfig.objects.filter(
            content_type=content_type,
            object_id=obj.pk
        ).first()
    except Exception:
        return None


def get_styles_for_queryset(queryset):
    """
    Efficiently prefetch styles for a queryset of objects.

    Args:
        queryset: Django QuerySet

    Returns:
        dict mapping object.pk to StyleConfig
    """
    if not queryset:
        return {}

    try:
        model_class = queryset.model
        content_type = ContentType.objects.get_for_model(model_class)

        object_ids = list(queryset.values_list('pk', flat=True))
        styles = StyleConfig.objects.filter(
            content_type=content_type,
            object_id__in=object_ids
        )

        # Create mapping: object_id -> StyleConfig
        return {style.object_id: style for style in styles}
    except Exception:
        return {}
```

### 5. Create Template Tags

**File**: `/myapp/reader/templatetags/reader_tags.py` (new file)

```python
"""Template tags for reader app styling."""
from django import template
from reader.utils import get_style_for_object

register = template.Library()


@register.simple_tag
def get_style(obj):
    """
    Get style configuration for an object.

    Usage in template:
        {% load reader_tags %}
        {% get_style section as style %}
        {% if style %}
            <div style="background-color: {{ style.color }};">
        {% endif %}
    """
    return get_style_for_object(obj)


@register.filter
def has_style(obj):
    """
    Check if object has a style configuration.

    Usage:
        {% if section|has_style %}
            ...
        {% endif %}
    """
    style = get_style_for_object(obj)
    return style is not None


@register.filter
def style_color(obj):
    """
    Get color from object's style.

    Usage:
        style="background-color: {{ section|style_color }};"
    """
    style = get_style_for_object(obj)
    return style.color if style else ''


@register.filter
def style_icon(obj):
    """
    Get icon from object's style.

    Usage:
        <i class="{{ section|style_icon }}"></i>
    """
    style = get_style_for_object(obj)
    return style.icon if style else ''
```

**Create template tags directory**:
```bash
mkdir -p /myapp/reader/templatetags
touch /myapp/reader/templatetags/__init__.py
```

## Database Migration Strategy

### Migration Steps

**Step 1: Create StyleConfig model in reader app**
```bash
# Add StyleConfig to reader/models.py
python manage.py makemigrations reader
python manage.py migrate reader
```

**Step 2: Remove icon/color fields from Section and Genre**
```bash
# Remove icon field from Section
# Remove icon and color fields from Genre
python manage.py makemigrations books
python manage.py migrate books
```

**Note**: We remove fields AFTER migrating data to StyleConfig to ensure no data loss.

**Step 3: Data migration - Copy icon/color to StyleConfig**

Create a data migration BEFORE removing fields:

```python
# reader/migrations/XXXX_migrate_styles_data.py
from django.db import migrations
from django.contrib.contenttypes.models import ContentType


def migrate_section_styles(apps, schema_editor):
    Section = apps.get_model('books', 'Section')
    StyleConfig = apps.get_model('reader', 'StyleConfig')
    ContentType = apps.get_model('contenttypes', 'ContentType')

    section_ct = ContentType.objects.get_for_model(Section)

    for section in Section.objects.all():
        if section.icon:  # Only create if there's data
            StyleConfig.objects.create(
                content_type=section_ct,
                object_id=section.id,
                icon=section.icon
            )


def migrate_genre_styles(apps, schema_editor):
    Genre = apps.get_model('books', 'Genre')
    StyleConfig = apps.get_model('reader', 'StyleConfig')
    ContentType = apps.get_model('contenttypes', 'ContentType')

    genre_ct = ContentType.objects.get_for_model(Genre)

    for genre in Genre.objects.all():
        if genre.icon or genre.color:  # Create if either exists
            StyleConfig.objects.create(
                content_type=genre_ct,
                object_id=genre.id,
                icon=genre.icon or '',
                color=genre.color or ''
            )


class Migration(migrations.Migration):
    dependencies = [
        ('reader', 'XXXX_create_styleconfig'),
        ('books', '____latest__'),  # Books app must exist
        ('contenttypes', '__latest__'),
    ]

    operations = [
        migrations.RunPython(migrate_section_styles),
        migrations.RunPython(migrate_genre_styles),
    ]
```

**Note**: This migration depends on books app but doesn't modify it - just reads data.

**Step 5: Update seed_taxonomy command**

Update `/myapp/books/management/commands/seed_taxonomy.py`:

```python
from reader.models import StyleConfig

# Create section first
fiction = Section.objects.create(
    name="Fiction",
    slug="fiction",
    # ... other fields (no icon field anymore)
)

# Then create its style using GenericForeignKey
StyleConfig.objects.create(
    content_object=fiction,  # Sets content_type and object_id automatically
    color='#3498db',
    icon='fas fa-book'
)

# Or manually:
# from django.contrib.contenttypes.models import ContentType
# section_ct = ContentType.objects.get_for_model(Section)
# StyleConfig.objects.create(
#     content_type=section_ct,
#     object_id=fiction.id,
#     color='#3498db',
#     icon='fas fa-book'
# )

# Repeat for other sections
bl = Section.objects.create(name="BL", slug="bl", ...)
StyleConfig.objects.create(content_object=bl, color='#e91e63', icon='fas fa-heart')

gl = Section.objects.create(name="GL", slug="gl", ...)
StyleConfig.objects.create(content_object=gl, color='#9c27b0', icon='fas fa-rainbow')

nonfiction = Section.objects.create(name="Non-fiction", slug="non-fiction", ...)
StyleConfig.objects.create(content_object=nonfiction, color='#4caf50', icon='fas fa-graduation-cap')
```

**Section Colors**:
- Fiction: `#3498db` (blue) - Traditional, trustworthy
- BL: `#e91e63` (pink/rose) - Romantic, warm
- GL: `#9c27b0` (purple) - Elegant, unique
- Non-fiction: `#4caf50` (green) - Fresh, educational

## CSS Implementation

### File: `/myapp/reader/static/reader/css/styles.css`

Add new section for styled navigation buttons:

```css
/* ===========================
   Section Navigation Buttons
   =========================== */

/* Base styling for section nav buttons */
.section-nav-btn {
    padding: 0.6rem 1.5rem;
    font-size: 1.1rem;
    font-weight: 600;
    border: none;
    color: white;
    transition: all 0.3s ease;
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    text-decoration: none;
}

.section-nav-btn:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 8px rgba(0, 0, 0, 0.15);
    filter: brightness(1.1);
    color: white;
}

.section-nav-btn.active {
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
    transform: translateY(-1px);
    filter: brightness(0.95);
}

/* Fallback color if section.color is not set */
.section-nav-btn:not([style*="background"]) {
    background-color: var(--color-primary);
}
```

**Key Features**:
- Large, pill-shaped buttons (`rounded-pill` from Bootstrap)
- Smooth transitions on hover
- Subtle shadow effects for depth
- Brightness filter for hover state
- Active state for current section
- Fallback to primary color if section color not set

## Template Updates

### File: `/myapp/reader/templates/reader/base.html`

**Section Nav (lines 99-122)**:

**Before**:
```django
<a href="{% url 'reader:section_home' current_language.code nav_section.slug %}"
   class="btn btn-sm {% if section and section.slug == nav_section.slug %}btn-primary-custom{% else %}btn-outline-primary-custom{% endif %}">
    {% if nav_section.icon %}<i class="{{ nav_section.icon }} me-1"></i>{% endif %}
    {{ nav_section.localized_name }}
</a>
```

**After (Option 1: Using template tag)**:
```django
{% load reader_tags %}

{% for nav_section in sections %}
    {% get_style nav_section as nav_style %}
    <a href="{% url 'reader:section_home' current_language.code nav_section.slug %}"
       class="section-nav-btn rounded-pill {% if section and section.slug == nav_section.slug %}active{% endif %}"
       {% if nav_style and nav_style.color %}style="background-color: {{ nav_style.color }};"{% endif %}
       data-ajax-nav="section"
       data-section-slug="{{ nav_section.slug }}">
        {% if nav_style and nav_style.icon %}<i class="{{ nav_style.icon }} me-1"></i>{% endif %}
        {{ nav_section.localized_name }}
    </a>
{% endfor %}
```

**After (Option 2: Using filters - cleaner)**:
```django
{% load reader_tags %}

{% for nav_section in sections %}
    <a href="{% url 'reader:section_home' current_language.code nav_section.slug %}"
       class="section-nav-btn rounded-pill {% if section and section.slug == nav_section.slug %}active{% endif %}"
       {% if nav_section|style_color %}style="background-color: {{ nav_section|style_color }};"{% endif %}
       data-ajax-nav="section"
       data-section-slug="{{ nav_section.slug }}">
        {% if nav_section|style_icon %}<i class="{{ nav_section|style_icon }} me-1"></i>{% endif %}
        {{ nav_section.localized_name }}
    </a>
{% endfor %}
```

**Key Changes**:
- Load `reader_tags` at top of template
- Use `{% get_style nav_section as nav_style %}` to fetch style (Option 1)
- Or use filters: `nav_section|style_color` and `nav_section|style_icon` (Option 2)
- Replace `btn btn-sm` with `section-nav-btn rounded-pill`
- Simplify active state: just add `active` class
- Keep existing `data-ajax-nav` attributes
- Null-safe: filters return empty string if no style

**Note**: Both options work. Option 2 (filters) is cleaner and more readable.

## Implementation Checklist

- [ ] Create StyleConfig model with GenericForeignKey in `/myapp/reader/models.py`
- [ ] Register StyleConfig in reader admin
- [ ] Create `/myapp/reader/utils.py` with helper functions
- [ ] Create `/myapp/reader/templatetags/` directory
- [ ] Create `/myapp/reader/templatetags/__init__.py`
- [ ] Create `/myapp/reader/templatetags/reader_tags.py` with template tags
- [ ] Create migration for reader app (StyleConfig with ContentType)
- [ ] Create data migration in reader app to copy icon/color from books
- [ ] Apply reader app migrations
- [ ] Remove icon field from Section model in books app
- [ ] Remove icon and color fields from Genre model in books app
- [ ] Create migration for books app (remove fields)
- [ ] Apply books app migration
- [ ] Update seed_taxonomy command to use GenericForeignKey
- [ ] Add `.section-nav-btn` CSS classes in `styles.css`
- [ ] Update base.html template to load `reader_tags` and use filters
- [ ] Test section navigation appearance in browser
- [ ] Verify null-safety when no style exists
- [ ] Test hover effects and active states
- [ ] Verify books app works independently (no imports from reader)

## Testing Plan

1. **Visual Testing**:
   - Check section nav on all pages
   - Verify colors render correctly
   - Test hover and active states
   - Check responsive behavior on mobile
   - Verify fallback color when section.color is empty

2. **Theme Testing**:
   - Test in light theme
   - Test in dark theme (white text should remain visible)

3. **Database Testing**:
   - Verify migration runs without errors
   - Check that existing sections work without color (graceful degradation)

## Future Enhancements (If Needed)

When we actually need more styling options, we can:

1. **Add More Fields**: Add fields like `font_weight`, `border_radius` directly to models
2. **Extract to StyleConfig**: Create a separate StyleConfig model with 1:1 relationship
3. **Admin Color Picker**: Add a visual color picker in Django admin
4. **CSS Variables**: Generate CSS custom properties from model data
5. **Gradient Support**: Add gradient color options

## Design Decisions

**Why StyleConfig in reader app?**
- Clear separation: books = business logic, reader = presentation
- StyleConfig is purely UI/presentation concern
- Can be extended for other reader UI elements
- Avoids mixing concerns in taxonomy models

**Why GenericForeignKey instead of OneToOneField?**
- ✅ **Zero dependency** from books → reader (books app is 100% independent!)
- ✅ **Universal styling**: Can style ANY model without code changes
- ✅ **Flexible**: Easy to add styling to Tag, BookMaster, or future models
- ✅ **Clean architecture**: Presentation depends on business, never reverse
- Trade-off: Slightly more complex queries (but we have efficient helper functions)

**Why helper functions instead of GenericRelation?**
- ✅ **True independence**: Books models have ZERO imports from reader
- ✅ **No string references**: No lazy loading of reader models in books app
- ✅ **Works standalone**: Books app functions perfectly even if reader is removed
- ✅ **Clean separation**: All styling logic lives in reader app where it belongs
- Trade-off: Slightly more verbose template code (use `{% load reader_tags %}`)

**Why custom_styles JSON field?**
- Extremely extensible without migrations
- Can add font_weight, border_radius, hover_color, etc. anytime
- Easy to experiment with new styles
- No schema changes needed for new properties
- Trade-off: Less type safety, but more flexibility

**Why inline styles in template?**
- Dynamic colors per section
- No need to generate CSS classes dynamically
- Simple template logic
- Good browser caching (template doesn't change, only data)

**Why not text color calculation?**
- CSS handles it: white text on colored background is the standard
- Can add dark theme handling in CSS if needed
- Keeps Python code simple
- Can add later in custom_styles if needed

## Future Extensions

Now that StyleConfig exists, you can easily add:

1. **New fields** directly to StyleConfig model:
   ```python
   font_weight = models.CharField(max_length=20, blank=True)
   border_radius = models.CharField(max_length=20, blank=True)
   ```

2. **Via custom_styles JSON** (no migration):
   ```python
   style.set_style_property('hover_color', '#FF8555')
   style.set_style_property('font_family', 'Roboto')
   ```

3. **Helper methods** for computed properties:
   ```python
   def get_hover_color(self):
       """Auto-generate hover color if not set"""
       return self.get_style_property('hover_color') or self.lighten_color()
   ```

4. **Reuse for other models**:
   ```python
   class Tag(TimeStampedModel):
       style = models.OneToOneField('reader.StyleConfig', ...)
   ```

5. **Admin improvements**:
   - Color picker widget
   - Icon selector
   - Preview of styled element
