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

## Working Directory

All Django management commands should be run from the `myapp/` directory, not the project root.

## Translation Workflow

The system supports a master-translation architecture:
1. **BookMaster/ChapterMaster** - Language-agnostic master entities
2. **Book/Chapter** - Language-specific translated versions
3. **TranslationJob** - Async translation processing with OpenAI API
4. **Language** - Configuration for different languages with reading speeds
5. **Publishing** - Independent publishing control per language version