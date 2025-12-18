# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Documentation Structure

All project documentation is organized in the `doc/` folder:

### Reference Documentation (Use These)
- **[doc/OPTIMIZATION_SUMMARY.md](doc/OPTIMIZATION_SUMMARY.md)** - Quick reference for query optimization patterns (use this first!)
- **[doc/optimization/MASTER_OPTIMIZATION_PLAN.md](doc/optimization/MASTER_OPTIMIZATION_PLAN.md)** - Complete optimization roadmap
- **[doc/TRANSLATION_REFACTORING_SUMMARY.md](doc/TRANSLATION_REFACTORING_SUMMARY.md)** - Quick reference for AI services refactoring
- **[doc/TRANSLATION_REFACTORING_PLAN.md](doc/TRANSLATION_REFACTORING_PLAN.md)** - Detailed plan for modular AI services architecture
- **[doc/DEVELOPMENT_TOOLS_SETUP.md](doc/DEVELOPMENT_TOOLS_SETUP.md)** - Silk and Locust setup guide
- **[doc/DOCKER_SETUP.md](doc/DOCKER_SETUP.md)** - Docker configuration and commands
- **[doc/RELATIONSHIPS_DIAGRAM.md](doc/RELATIONSHIPS_DIAGRAM.md)** - Database relationships overview
- **[doc/TEMPLATE_TAG_QUERY_MIGRATION.md](doc/TEMPLATE_TAG_QUERY_MIGRATION.md)** - Template tag optimization guide

### Historical Documentation (Reference Only)
- `doc/optimization/` - Original optimization planning documents
- `doc/reports/` - Completion reports from optimization work (Week 1-3)
- `doc/features/` - SEO implementation documentation

**When working on optimization tasks, always consult [doc/OPTIMIZATION_SUMMARY.md](doc/OPTIMIZATION_SUMMARY.md) first for current best practices.**

## Project Overview

This is a Django web application for translating webnovels using OpenAI API. The project is structured as a standard Django application with apps for user management and book/translation functionality.

## Development Commands

### Setup and Installation
```bash
# Initialize virtual enviroment
python3.12 -m venv .venv

# Activate virtual enviroment
source ./.venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run migrations
python myapp/manage.py migrate

# Create superuser
python myapp/manage.py createsuperuser

# Run development server
python myapp/manage.py runserver
```

### Development Tasks
```bash
# Run Django development server
source ./.venv/bin/activate && cd myapp && python manage.py runserver

# Create and apply migrations
source ./.venv/bin/activate && cd myapp && python manage.py makemigrations
source ./.venv/bin/activate && cd myapp && python manage.py migrate

# Access Django admin
# Navigate to http://127.0.0.1:8000/admin/ after running server

# Django shell for debugging
source ./.venv/bin/activate &&  cd myapp && python manage.py shell
```

## Architecture

### Project Structure
- `myapp/` - Main Django project directory
  - `myapp/` - Core Django settings and configuration
  - `accounts/` - User management with custom User model and role-based system
  - `books/` - Book/webnovel models and translation functionality
  - `translation/` - Translation-related functionality (placeholder app)
  - `common/` - Shared utilities and base models (TimeStampedModel)

### Key Components

**User System (`accounts/`)**
- Custom User model extending AbstractUser with role-based permissions
- Three user roles: Reader, Translator, Admin (defined in `accounts/choices.py`)
- User model includes optional pen_name field for display purposes
- Database indexes on role and active status for performance

**Configuration**
- Uses environment variables for sensitive settings (SECRET_KEY, DEBUG, ALLOWED_HOSTS)
- SQLite database for development (configured in settings.py)
- Standard Django middleware stack
- Settings configured for development with proper environment variable handling

### Database Models

#### User Management (`accounts/`)

**User Model** (`accounts/models.py:7`)
- Extends Django's AbstractUser with custom fields
- Role field with choices: Reader (default), Translator, Admin
- Optional pen_name field for display purposes
- Custom display_name property that prefers pen_name over username
- Database indexes on role and [is_active, role] for performance

**Role Choices** (`accounts/choices.py:4`)
- TextChoices enum: READER, TRANSLATOR, ADMIN

#### Book and Translation System (`books/`)

**Common Base Models** (`common/models.py`)
- TimeStampedModel: Abstract base with created_at and updated_at fields
- Used by all models for consistent timestamping

**Language Model** (`books/models.py:45`)
- Language configuration for translations
- Fields: code (unique), name, local_name, count_units, wpm (reading speed)
- Count units: WORDS or CHARS for different languages
- WPM field for calculating reading time estimates

**BookMaster Model** (`books/models.py:62`)
- Master book entity for managing translations across languages
- Fields: canonical_title, cover_image, owner (User FK), original_language (Language FK)
- One BookMaster can have multiple Book instances in different languages
- Defaults to Chinese (zh) as original language if not specified

**Book Model** (`books/models.py:103`)
- Language-specific version of a book
- Fields: title, slug (unique), author, description, cover_image
- Relationships: bookmaster (FK), language (FK)
- Publishing: is_public, progress (draft/ongoing/completed), published_at
- Metadata: total_chapters, total_words, total_characters (auto-calculated)
- SlugGeneratorMixin for automatic unique slug generation
- Properties: effective_count, reading_time_minutes, effective_cover_image

**ChapterMaster Model** (`books/models.py:200`)
- Master chapter entity for managing chapter translations
- Fields: canonical_title, bookmaster (FK), chapter_number
- Ordered by chapter_number for consistent sequencing

**Chapter Model** (`books/models.py:221`)
- Language-specific chapter content
- Fields: title, slug, content (TextField), excerpt, word_count, character_count
- Relationships: chaptermaster (FK), book (FK)
- Publishing: is_public, progress (draft/translating/completed), scheduled_at, published_at
- SlugGeneratorMixin for unique slugs within book scope
- Auto-calculates word/character counts on save
- Methods: generate_excerpt(), publish(), unpublish()
- Properties: effective_count, reading_time_minutes

**TranslationJob Model** (`books/models.py:321`)
- Async translation job tracking
- Fields: chapter (FK), target_language (FK), status, created_by (User FK), error_message
- Status choices: pending, processing, completed, failed
- Used for OpenAI API translation workflows

#### Choice Fields (`books/choices.py`)
- BookProgress: DRAFT, ONGOING, COMPLETED
- ChapterProgress: DRAFT, TRANSLATING, COMPLETED  
- ProcessingStatus: PENDING, PROCESSING, COMPLETED, FAILED
- CountUnits: WORDS, CHARS (for different language counting methods)
- Rating: EVERYONE, TEEN, MATURE, ADULT (defined but not used yet)

#### Database Indexes
Performance optimized with indexes on:
- User: role, [is_active, role]
- BookMaster: canonical_title, owner
- Book: created_at, [language, is_public], [is_public, progress]
- ChapterMaster: canonical_title, bookmaster, chapter_number
- Chapter: [book, is_public], [is_public, progress], [published_at, is_public], scheduled_at
- TranslationJob: status, created_at

#### Unique Constraints
- Language.code: Globally unique
- Book.slug: Globally unique
- Chapter: [book, slug] - unique slug within each book

#### Django Admin Configuration

All models are registered in Django admin with comprehensive interfaces:

**User Admin** (`accounts/admin.py:7`)
- List display: username, email, role, pen_name, is_active, is_staff, date_joined
- Filtering: role, is_active, is_staff, is_superuser
- Search: username, email, pen_name
- Custom fieldsets include role and pen_name fields

**Books Admin** (`books/admin.py`)
- LanguageAdmin: List/search by name, code, local_name
- BookMasterAdmin: List by canonical_title, owner, original_language
- BookAdmin: Comprehensive view with prepopulated slug, readonly metadata
- ChapterMasterAdmin: Organized by bookmaster and chapter_number
- ChapterAdmin: Full chapter management with prepopulated slug, readonly counts
- TranslationJobAdmin: Job monitoring with status/language filtering

## Environment Setup

The application expects these environment variables:
- `DJANGO_SECRET_KEY` - Django secret key (required)
- `DJANGO_DEBUG` - Set to "TRUE" for debug mode (defaults to True)
- `ENVIRONMENT` - Set to "development" or "production" (controls development tools like Silk and Debug Toolbar)
- `DJANGO_ALLOWED_HOSTS` - Comma-separated list of allowed hosts (defaults to localhost,127.0.0.1)
- `DISABLE_CACHE` - Set to "True" to disable Redis cache layer and always hit database (useful for development to avoid stale data confusion)

### Development vs Production

The project uses the `ENVIRONMENT` variable to control which tools are loaded:

**Development Mode** (`ENVIRONMENT=development`):
- Enables Django Silk for request profiling and query analysis
- Enables Django Debug Toolbar
- Both tools are automatically disabled when `ENVIRONMENT=production`

**Production Mode** (`ENVIRONMENT=production`):
- All development tools disabled
- Enhanced security settings enabled
- System checks prevent accidental development tool deployment

See [DEVELOPMENT_TOOLS_SETUP.md](doc/DEVELOPMENT_TOOLS_SETUP.md) for detailed setup instructions.

## Working Directory

All Django management commands should be run from the `myapp/` directory, not the project root.

## Translation Workflow

The system supports a master-translation architecture:
1. **BookMaster/ChapterMaster** - Language-agnostic master entities
2. **Book/Chapter** - Language-specific translated versions
3. **TranslationJob** - Async translation processing with OpenAI API
4. **Language** - Configuration for different languages with reading speeds
5. **Publishing** - Independent publishing control per language version

## Hierarchical Taxonomy System

### Overview

The application uses a comprehensive hierarchical taxonomy system for organizing books:

- **Sections**: Top-level categories (Fiction, BL, GL, Non-fiction)
- **Genres**: Hierarchical genre system with primary and sub-genres
- **Tags**: Flexible tagging for book attributes
- **Keywords**: Denormalized search index for fast multi-language search

### Database Models

#### Section (`books.models.Section`)

Top-level content category.

**Fields**:
- `name`: Section name (e.g., "Fiction", "BL")
- `slug`: URL-friendly identifier
- `description`: Section description
- `icon`: FontAwesome icon class
- `order`: Display order
- `is_mature`: Whether section contains mature content
- `translations`: JSON field for localized names

**Usage**:
```python
from books.models import Section

fiction = Section.objects.get(slug='fiction')
print(fiction.get_localized_name('zh'))  # "小说"
```

#### Genre (`books.models.Genre`)

Hierarchical genre classification.

**Fields**:
- `section`: ForeignKey to Section
- `name`: Genre name
- `slug`: URL-friendly identifier (unique within section)
- `parent`: ForeignKey to self (for sub-genres)
- `is_primary`: Whether genre is primary (True) or sub-genre (False)
- `icon`: FontAwesome icon
- `color`: Hex color code
- `translations`: JSON field for localized names

**Hierarchy Rules**:
1. Primary genres (`is_primary=True`) cannot have parents
2. Sub-genres (`is_primary=False`) must have a primary parent
3. Parent and child must belong to same section
4. No self-references or circular references

**Usage**:
```python
from books.models import Genre

# Get primary genre
fantasy = Genre.objects.get(section__slug='fiction', slug='fantasy')

# Get sub-genres
sub_genres = fantasy.sub_genres.all()
```

#### BookGenre Through Model

Ordered many-to-many relationship between BookMaster and Genre.

**Fields**:
- `bookmaster`: ForeignKey to BookMaster
- `genre`: ForeignKey to Genre
- `order`: Display order

**Validation**:
- All genres must belong to BookMaster's section
- Cannot change BookMaster section if incompatible genres exist

#### Tag (`books.models.Tag`)

Flexible tagging system.

**Categories**:
- `protagonist`: Protagonist traits
- `relationship`: Relationship dynamics
- `plot`: Plot elements
- `setting`: Setting/world-building
- `tone`: Story tone

**Usage**:
```python
from books.models import Tag

# Get tags by category
protagonist_tags = Tag.objects.filter(category='protagonist')
```

#### BookKeyword (`books.models.BookKeyword`)

Denormalized search index for fast keyword lookups.

**Auto-Generated**: Keywords are automatically generated from:
- Section names (weight: 1.5)
- Genre names (weight: 1.0)
- Tag names (weight: 0.8)
- Entity names (weight: 0.6)

**Fields**:
- `bookmaster`: ForeignKey to BookMaster
- `keyword`: Searchable keyword
- `keyword_type`: Type (section, genre, tag, entity_*)
- `language_code`: Language of keyword
- `weight`: Relevance weight for ranking

### Search System

The search system uses BookKeyword for fast, weighted keyword search:

```python
from books.utils.search import BookSearchService

result = BookSearchService.search(
    query='cultivation fantasy',
    language_code='en',
    section_slug='fiction',
    limit=20
)

print(f"Found {result['total_results']} books in {result['search_time_ms']}ms")
for book in result['books']:
    print(book.title)
```

**Search Algorithm**:
1. Normalize and tokenize query
2. Find matching keywords
3. Calculate relevance scores (keyword_weight × match_type_weight)
4. Aggregate scores by BookMaster
5. Apply filters (section, genre, tag, status)
6. Return ranked results

### Admin Usage

#### Creating Genres

1. Go to Django Admin → Taxonomy - Genres → Add Genre
2. Select Section (required)
3. Choose whether Primary or Sub-genre
4. If sub-genre, select Parent (only shows same-section primary genres)
5. Add translations for multi-language support

**Validation**:
- Parent dropdown automatically filters by selected section
- Cannot set genre as its own parent
- Clear error messages guide you to fix issues

#### Creating Books with Taxonomy

1. Go to Django Admin → Core - Book Masters → Add Book Master
2. Set Section
3. Add Genres inline (only shows genres from selected section)
4. Add Tags inline
5. Save

**Validation**:
- Cannot change section if incompatible genres exist
- Warning shown if no genres assigned
- Warning shown if only sub-genres assigned

### Management Commands

#### Seed Taxonomy Data

```bash
# Seed comprehensive taxonomy data
python manage.py seed_taxonomy

# Clear existing data and re-seed
python manage.py seed_taxonomy --clear
```

Creates:
- 4 Sections (Fiction, BL, GL, Non-fiction)
- 20 Genres with hierarchies
- 15 Tags across categories
- 4 Sample books with complete taxonomy

#### Run Tests

```bash
# Run all taxonomy tests
python manage.py test books.tests.test_taxonomy

# Run specific test class
python manage.py test books.tests.test_taxonomy.GenreValidationTestCase

# Run with verbose output
python manage.py test books.tests.test_taxonomy -v 2
```

Test coverage includes:
- Genre validation (hierarchy rules, self-references, circular references)
- BookMaster validation (section changes, genre compatibility)
- Search functionality (keyword matching, filtering)
- Integration workflows (complete book setup, section changes)

## Query Optimization Patterns

The reader app has been extensively optimized to minimize database queries and maximize performance. All new code should follow these established patterns.

### Performance Achievements

| View | Baseline | Optimized | Reduction | Time |
|------|----------|-----------|-----------|------|
| Homepage | 74 queries | 11 queries | 85.1% | 21ms |
| Section Home | 74 queries | 18 queries | 75.7% | 46ms |
| Book Detail | 74 queries | 33 queries | 55.4% | 98ms |

**Key Optimizations**:
- All N+1 patterns eliminated
- Redis cache enabled (90%+ hit rate)
- Optimized prefetch patterns throughout
- Bulk operations instead of per-item queries

### 1. Using Optimized QuerySets

**Location**: `books/models/core.py` (Lines 215-480)

The `Book` model has a custom manager with optimized querysets. **Always use these methods instead of basic queryset operations.**

#### For List Views (Book Cards)

```python
# ✅ CORRECT - Use optimized queryset
from books.models import Book

books = Book.objects.for_list_display(language_code, section_slug)
# Result: ~6-8 queries for any number of books (uses prefetch)

# ❌ WRONG - Basic queryset causes N+1 queries
books = Book.objects.filter(language__code=language_code).select_related('bookmaster')
# Result: 20+ queries for 6 books (N+1 on genres, tags, stats)
```

**What `.for_list_display()` includes**:
- BookMaster, Section, Author (select_related)
- Genres with hierarchy (optimized Prefetch + select_related)
- Tags (only needed fields)
- Entities (only needed fields)
- BookStats, ChapterStats (select_related, not prefetch)
- Language (select_related)

#### For Detail Views

```python
# ✅ CORRECT - Use detail queryset
book = Book.objects.for_detail_display(language_code, section_slug).get(slug=slug)
# Result: All related data prefetched, no additional queries in template

# ❌ WRONG - Basic get() causes template queries
book = Book.objects.get(slug=slug)
# Result: Every {{ book.bookmaster.genres.all }} triggers new query
```

**What `.for_detail_display()` adds**:
- Everything from `.for_list_display()`
- Plus: Chapters with stats (for chapter list)
- Plus: Full chapter navigation data

#### For Card Relations Only

```python
# ✅ For views that ONLY need card data (no extra filtering)
books = Book.objects.with_card_relations().filter(is_public=True)
# Result: Optimized prefetch without language/section filters
```

### 2. View-Level Enrichment Patterns

**Location**: `reader/views/base.py` (Lines 177-363)

Views should enrich data ONCE and pass to templates. **Never let templates query the database.**

#### Single Book Enrichment

```python
# In your view's get_context_data() or get()
def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    language_code = self.kwargs.get("language_code")

    # ✅ CORRECT - Enrich book once in view
    book = self.object
    self.enrich_book_with_metadata(book, language_code)
    # Now book has: localized names, chapter counts, views, organized tags

    context['book'] = book
    return context

# Template can now use {{ book.enriched_genres }}, {{ book.tags_by_category }} with 0 queries
```

#### Multiple Books Enrichment (List Views)

```python
# In your view's get_context_data()
def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    language_code = self.kwargs.get("language_code")
    books = context['object_list']  # From ListView

    # ✅ CORRECT - Bulk enrichment (GROUP BY for new chapters)
    enriched_books = self.enrich_books_with_metadata(books, language_code)
    # Single bulk query for new chapters count across ALL books

    context['object_list'] = enriched_books
    return context

# Template can access {{ book.new_chapters_count }} with 0 additional queries
```

**What enrichment adds**:
- `book.published_chapters_count` - From cache
- `book.total_chapter_views` - From cache
- `book.new_chapters_count` - Bulk calculated
- `book.enriched_genres` - List with localized names
- `book.tags_by_category` - Dict grouped by category
- `book.entities_by_type` - Dict grouped by type
- `book.section_localized_name` - Localized section name
- `book.author_localized_name` - Localized author name

### 3. Aggregation Queries for Statistics

**Location**: `reader/views/section.py` (Lines 295-379)

Use Django's aggregation to replace multiple queries with single query.

```python
# ✅ CORRECT - Single aggregation query
from django.db.models import Count, Sum, Max

chapter_stats = book.chapters.filter(is_public=True).aggregate(
    total_chapters=Count('id'),
    total_words=Sum('word_count'),
    total_characters=Sum('character_count'),
    last_update=Max('published_at')
)

context['total_chapters'] = chapter_stats['total_chapters'] or 0
context['total_words'] = chapter_stats['total_words'] or 0
context['last_update'] = chapter_stats['last_update']
# Result: 1 query for all statistics

# ❌ WRONG - Multiple separate queries
context['total_chapters'] = book.chapters.filter(is_public=True).count()  # Query 1
context['total_words'] = sum(ch.word_count for ch in book.chapters.all())  # Query 2 + loads ALL chapters
context['last_update'] = book.chapters.filter(is_public=True).order_by('-published_at').first()  # Query 3
# Result: 3 queries + memory overhead
```

### 4. Prefetch with to_attr Pattern

**Location**: `reader/views/section.py` (Lines 260-293)

For data that needs zero-query access in templates, use `to_attr`.

```python
from django.db.models import Prefetch
from books.models import Book

# ✅ CORRECT - Prefetch with to_attr for zero-query access
hreflang_prefetch = Prefetch(
    'bookmaster__books',
    queryset=Book.objects.filter(is_public=True).select_related('language'),
    to_attr='hreflang_books_list'  # ← Stores as Python list attribute
)

queryset = Book.objects.prefetch_related(hreflang_prefetch)

# In template or view:
book.bookmaster.hreflang_books_list  # ← 0 queries (Python list)

# ❌ WRONG - Without to_attr
queryset = Book.objects.prefetch_related('bookmaster__books')
book.bookmaster.books.all()  # ← May still trigger query if filtered
```

### 5. Template Tag Optimization

**Location**: `reader/templatetags/reader_extras.py` (Lines 515-528)

Template tags should use context data, not query database.

```python
# ✅ CORRECT - Context-aware template tag
@register.simple_tag(takes_context=True)
def hreflang_tags(context, bookmaster):
    # Try to use prefetched data from view context first
    hreflang_books = context.get('hreflang_books')

    if hreflang_books is not None:
        # Use prefetched data (0 queries)
        related_books = hreflang_books
    else:
        # Fallback: Query database (backwards compatible)
        related_books = Book.objects.filter(
            bookmaster=bookmaster,
            is_public=True
        ).select_related('language')

    return generate_hreflang_html(related_books)

# ❌ WRONG - Always queries database
@register.simple_tag
def hreflang_tags(bookmaster):
    # Every call triggers query, even if data is prefetched
    books = Book.objects.filter(bookmaster=bookmaster)
    return generate_hreflang_html(books)
```

### 6. StyleConfig Bulk Prefetch

**Location**: `reader/views/base.py` (Lines 420-479)

StyleConfig (colors, icons for sections/genres) must be bulk prefetched.

```python
# In view's get_context_data()
def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)

    # ✅ CORRECT - Bulk prefetch ALL styles at once
    context = self._prefetch_styles_for_context(context)
    # Result: 2-3 bulk queries for ALL sections/genres/tags styles

    return context

# Template can now use filters with 0 queries:
# {{ section|style_color }}  ← 0 queries (uses cached _cached_style)
# {{ genre|style_icon }}     ← 0 queries

# ❌ WRONG - Let template tags query individually
# Result: 20-40 queries (1 per section/genre displayed)
```

### 7. Cache Usage Patterns

**Location**: `reader/cache/` directory

Use cache for data that rarely changes.

```python
from reader.cache import cache

# ✅ CORRECT - Use cached functions
languages = cache.get_cached_languages(user=request.user)  # 0 queries on 2nd call
sections = cache.get_cached_sections(user=request.user)    # 0 queries on 2nd call
genres = cache.get_cached_genres_flat()                    # 0 queries on 2nd call

# Bulk cache operations
chapter_counts = cache.get_cached_chapter_counts_bulk([1, 2, 3, 4, 5])  # 1 query for all

# ❌ WRONG - Query database directly
languages = Language.objects.filter(is_accessible=True)  # Always queries
for book in books:
    count = Chapter.objects.filter(book=book).count()  # N queries
```

**Cache TTLs** (configured in settings.py):
- Navigation data (languages, sections, genres): 3600s (1 hour)
- Metadata (chapter counts, views): 1800s (30 minutes)
- Homepage carousels: 900s (15 minutes)
- Taxonomy (tags, entities): 600s (10 minutes)

### 8. Common Anti-Patterns to Avoid

#### ❌ Anti-Pattern 1: Nested Prefetch Without Prefetch Objects

```python
# ❌ WRONG - Creates 3 separate queries
books = Book.objects.prefetch_related(
    'bookmaster__genres',
    'bookmaster__genres__section',
    'bookmaster__genres__parent'
)
# Result: Query 1: genres, Query 2: sections, Query 3: parents

# ✅ CORRECT - Use Prefetch with select_related
from django.db.models import Prefetch
from books.models import Genre

books = Book.objects.prefetch_related(
    Prefetch(
        'bookmaster__genres',
        queryset=Genre.objects.select_related('section', 'parent')
    )
)
# Result: 1 query with JOINs
```

#### ❌ Anti-Pattern 2: Using Prefetch for OneToOne

```python
# ❌ WRONG - Prefetch for OneToOne creates extra query
books = Book.objects.prefetch_related('bookstats')

# ✅ CORRECT - Use select_related for OneToOne/ForeignKey
books = Book.objects.select_related('bookstats')
```

#### ❌ Anti-Pattern 3: Template Loops with .count()

```django
{# ❌ WRONG - Queries in template loop #}
{% for book in books %}
    {{ book.chapters.count }} chapters  {# ← N queries! #}
{% endfor %}

{# ✅ CORRECT - Use pre-calculated count #}
{% for book in books %}
    {{ book.published_chapters_count }} chapters  {# ← 0 queries (from enrichment) #}
{% endfor %}
```

#### ❌ Anti-Pattern 4: Loading Full Objects When only() Suffices

```python
# ❌ WRONG - Loads all fields (more memory, slower)
tags = Tag.objects.all()

# ✅ CORRECT - Only load needed fields
tags = Tag.objects.only('id', 'name', 'slug', 'category')
# Result: 60% less memory, faster query
```

### 9. Adding New Views - Checklist

When creating new views that display books:

1. ✅ Use appropriate queryset method:
   - List views: `.for_list_display(lang, section)`
   - Detail views: `.for_detail_display(lang, section)`
   - Simple cards: `.with_card_relations()`

2. ✅ Enrich books in `get_context_data()`:
   - Single book: `self.enrich_book_with_metadata(book, language_code)`
   - Multiple books: `self.enrich_books_with_metadata(books, language_code)`

3. ✅ Prefetch styles for sections/genres/tags:
   - Call `context = self._prefetch_styles_for_context(context)`

4. ✅ Use aggregation for statistics:
   - Replace `.count()` + iteration with `.aggregate(Count, Sum, Max)`

5. ✅ Test with Django Debug Toolbar:
   - Check query count
   - Look for "Similar queries" (N+1 patterns)
   - Look for "Duplicate queries"
   - Verify cache is being used

### 10. Debugging Query Performance

**Tools**:
1. Django Debug Toolbar - Shows all queries for current request
2. `DISABLE_CACHE=True` in .env - Bypass cache to see actual query count
3. Shell testing - Verify prefetch works before deploying

**Shell Testing Pattern**:
```bash
# Test in Django shell
python manage.py shell
```

```python
from django.test.utils import override_settings
from django.db import connection
from django.db import reset_queries

# Reset query counter
reset_queries()

# Run your code
from books.models import Book
books = Book.objects.for_list_display('en', 'fiction')[:6]

# Force evaluation
list(books)

# Check query count
print(f"Queries: {len(connection.queries)}")

# Check what was queried
for query in connection.queries:
    print(query['sql'][:100])
```

### Summary of Optimization Principles

1. **Prefetch Everything**: Related data should be prefetched, not lazy-loaded
2. **Enrich in Views**: Calculate/localize once, not per template access
3. **Bulk Operations**: GROUP BY instead of N individual queries
4. **Cache Aggressively**: Navigation/taxonomy data rarely changes
5. **Use only()**: Don't load fields you won't use
6. **Aggregate Statistics**: COUNT/SUM/MAX in database, not Python
7. **Zero Template Queries**: Templates display data, never fetch it
8. **Test with Toolbar**: Always verify query count before deploying

**Reference Documentation**:
- [MASTER_OPTIMIZATION_PLAN.md](doc/optimization/MASTER_OPTIMIZATION_PLAN.md) - Complete optimization roadmap
- [OPTIMIZATION_SUMMARY.md](doc/OPTIMIZATION_SUMMARY.md) - Quick reference
- [OPTIMIZED_BOOK_QUERYSET.py](OPTIMIZED_BOOK_QUERYSET.py) - BookQuerySet implementation details