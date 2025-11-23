# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

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
- `DJANGO_ALLOWED_HOSTS` - Comma-separated list of allowed hosts (defaults to localhost,127.0.0.1)
- `DISABLE_CACHE` - Set to "True" to disable Redis cache layer and always hit database (useful for development to avoid stale data confusion)

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