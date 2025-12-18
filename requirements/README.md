# Requirements Files Structure

This directory contains organized requirements files for different environments.

## File Structure

```
requirements/
├── base.txt         # Core dependencies needed in all environments
├── development.txt  # Development tools (includes base.txt)
├── production.txt   # Production-only dependencies (includes base.txt)
└── README.md       # This file
```

## Usage

### Local Development (Docker)

The Dockerfile uses `requirements/development.txt`:

```dockerfile
RUN pip install -r requirements/development.txt
```

This includes:
- All base dependencies
- Django Debug Toolbar
- Django Silk (SQL profiling)
- Django Rosetta (i18n management)
- Locust (load testing)
- pytest (testing)
- ipython (better shell)

### Production Deployment (Railway)

Railway uses `requirements/production.txt` via the start script:

```bash
pip install -r requirements/production.txt
```

This includes:
- All base dependencies
- Gunicorn (production server)
- NO development tools (Silk, Debug Toolbar, Rosetta)

### Legacy Root requirements.txt

The root `requirements.txt` is kept for backward compatibility with Railway's default build process. It contains all dependencies but should eventually be phased out in favor of the structured approach.

**Recommendation**: Update Railway build command to use `requirements/production.txt`.

## What's in Each File?

### base.txt
Core dependencies needed everywhere:
- Django 5.2.5
- PostgreSQL driver (psycopg2-binary)
- Redis & Celery (background tasks)
- OpenAI SDK (translations)
- Static files (Whitenoise)
- Image handling (Pillow)
- S3 storage (boto3, django-storages)
- Forms (crispy-forms, crispy-bootstrap5)

### development.txt
Adds development tools:
- **django-debug-toolbar** - Debug panel in browser
- **django-silk** - SQL query profiling
- **django-rosetta** - Translation file management
- **locust** - Load testing
- **pytest & pytest-django** - Testing framework
- **ipython** - Enhanced Python shell

### production.txt
Adds production requirements:
- **gunicorn** - WSGI server for production
- (Optional) **sentry-sdk** - Error tracking (commented out)

## Environment Configuration

Development tools are only loaded when `ENVIRONMENT=development`:

**settings.py:**
```python
IS_DEVELOPMENT = os.getenv("ENVIRONMENT", "production") == "development"

if IS_DEVELOPMENT:
    INSTALLED_APPS += [
        "rosetta",
        "silk",
        "debug_toolbar",
    ]
```

**Docker** (local): `ENVIRONMENT=development` (from .env)
**Railway** (production): `ENVIRONMENT=production` (set in Railway dashboard)

## Updating Dependencies

1. **Add to base.txt** if needed everywhere (production + development)
2. **Add to development.txt** if only needed for local development
3. **Add to production.txt** if only needed in production

After updating, rebuild Docker:
```bash
docker-compose build --no-cache
docker-compose up -d
```
