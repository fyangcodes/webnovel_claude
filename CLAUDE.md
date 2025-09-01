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
  - `books/` - Book/webnovel models and translation functionality (models not yet implemented)
  - `common/` - Shared utilities and models (currently empty)

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

**User Model** (`accounts/models.py:7`)
- Extends Django's AbstractUser
- Role field with choices from RoleChoice enum
- Optional pen_name field for display
- Custom display_name property that prefers pen_name over username

**RoleChoice** (`accounts/choices.py:4`)
- TextChoices enum with Reader, Translator, Admin roles

## Environment Setup

The application expects these environment variables:
- `DJANGO_SECRET_KEY` - Django secret key (required)
- `DJANGO_DEBUG` - Set to "TRUE" for debug mode (defaults to True)
- `DJANGO_ALLOWED_HOSTS` - Comma-separated list of allowed hosts (defaults to localhost,127.0.0.1)

## Working Directory

All Django management commands should be run from the `myapp/` directory, not the project root.