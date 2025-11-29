# Development Tools Configuration Summary

## Overview

This project now includes comprehensive development tools for performance testing and profiling, configured to **automatically disable in production**.

## What Was Added

### 1. Django Silk (Request Profiling)
- **Purpose**: Profile SQL queries, detect N+1 problems, analyze request performance
- **URL**: `http://127.0.0.1:8000/silk/` (development only)
- **Auto-disabled** when `ENVIRONMENT=production`

### 2. Locust (Load Testing)
- **Purpose**: Simulate concurrent users, measure p95 response times
- **URL**: `http://localhost:8089` (run separately from Django)
- **File**: `locustfile.py` in project root

### 3. Safety Mechanisms

Multiple layers ensure development tools never run in production:

| Layer | How It Works |
|-------|-------------|
| **Environment Variable** | `ENVIRONMENT=development` required to load tools |
| **Conditional Settings** | Tools only added to `INSTALLED_APPS` if `IS_DEVELOPMENT=True` |
| **Separate Requirements** | `requirements/development.txt` vs `requirements/production.txt` |
| **Django System Checks** | `python manage.py check --deploy` shows errors if tools enabled in production |
| **URL Guards** | Tool URLs only registered if apps are installed |

## Quick Start

### Development Setup

```bash
# 1. Install development dependencies
pip install -r requirements/development.txt

# 2. Set environment (in .env file)
ENVIRONMENT=development

# 3. Run migrations (Silk creates tables)
cd myapp
python manage.py migrate

# 4. Start server
python manage.py runserver

# 5. Access tools
# - Django Silk: http://127.0.0.1:8000/silk/
# - Debug Toolbar: Appears on all pages
```

### Production Deployment

```bash
# 1. Install production dependencies only
pip install -r requirements/production.txt

# 2. Set environment
export ENVIRONMENT=production
export DJANGO_DEBUG=False

# 3. Verify no development tools
python manage.py check --deploy
# Should show: "System check identified no issues"

# 4. Deploy safely
# Silk and Debug Toolbar will NOT be installed or loaded
```

## File Changes

### New Files

```
requirements/
├── base.txt                    # Core dependencies
├── development.txt             # + Silk, Locust, testing tools
└── production.txt              # + Production server (gunicorn)

myapp/myapp/checks.py           # Django system checks
locustfile.py                   # Locust load testing script
.env.production.example         # Production environment template
DEVELOPMENT_TOOLS_SETUP.md      # Comprehensive guide
DEVELOPMENT_TOOLS_README.md     # This file
```

### Modified Files

```
myapp/myapp/settings.py         # Added IS_DEVELOPMENT flag, conditional Silk config
myapp/myapp/urls.py             # Conditional Silk URLs
myapp/books/apps.py             # Register system checks
.env                            # Added ENVIRONMENT=development
CLAUDE.md                       # Updated with development tools info
```

## Environment Variables

### .env (Development)
```bash
ENVIRONMENT=development     # Enables Silk and Debug Toolbar
DJANGO_DEBUG=True
```

### Production Environment
```bash
ENVIRONMENT=production      # Disables all development tools
DJANGO_DEBUG=False
```

## Testing the Configuration

### Test Development Mode
```bash
export ENVIRONMENT=development
python manage.py check
# Output: "🔧 Development mode: Silk and Debug Toolbar enabled"
# Result: System check identified no issues
```

### Test Production Mode
```bash
export ENVIRONMENT=production
export DJANGO_DEBUG=False
python manage.py check --deploy
# Result: No errors about Silk or Debug Toolbar
```

### Verify Tools Not Loaded
```python
python manage.py shell

from django.conf import settings
print('silk' in settings.INSTALLED_APPS)  # Should be False in production
print(settings.IS_DEVELOPMENT)             # Should be False in production
```

## Using the Tools

### Django Silk

1. Make requests to your app
2. Visit `http://127.0.0.1:8000/silk/`
3. Click on a request to see:
   - SQL queries executed
   - Query execution time
   - N+1 query detection
   - Python profiler data

**Cleaning up:**
```bash
python manage.py silk_clear_request_log
```

### Locust

```bash
# Start Locust web UI
locust -f locustfile.py

# Open browser: http://localhost:8089
# Configure users: 100
# Spawn rate: 10/second
# Start swarming

# Or run headless
locust -f locustfile.py --headless --users 100 --spawn-rate 10 --run-time 5m
```

## Day 16-17 Load Testing Workflow

From [MASTER_OPTIMIZATION_PLAN.md](MASTER_OPTIMIZATION_PLAN.md):

### Goals
- Homepage p95 < 200ms
- Book list p95 < 300ms
- Book detail p95 < 200ms
- No database connection exhaustion

### Steps

1. **Profile with Silk** (find bottlenecks)
   ```bash
   # Start server, make requests, review in /silk/
   ```

2. **Load test with Locust** (verify at scale)
   ```bash
   locust -f locustfile.py
   # Test with 100 concurrent users
   ```

3. **Fix issues**, re-test

4. **Deploy** (tools auto-disabled)

## Common Commands

```bash
# Development
pip install -r requirements/development.txt
export ENVIRONMENT=development
python manage.py runserver

# Production
pip install -r requirements/production.txt
export ENVIRONMENT=production
python manage.py check --deploy

# Load testing
locust -f locustfile.py --headless --users 100 --spawn-rate 10 --run-time 5m

# Clear Silk data
python manage.py silk_clear_request_log
```

## Documentation

- [DEVELOPMENT_TOOLS_SETUP.md](DEVELOPMENT_TOOLS_SETUP.md) - Complete guide
- [MASTER_OPTIMIZATION_PLAN.md](MASTER_OPTIMIZATION_PLAN.md) - Optimization roadmap
- [Django Silk Docs](https://github.com/jazzband/django-silk)
- [Locust Docs](https://docs.locust.io/)

## Troubleshooting

### Silk not showing up?
```bash
# Check environment
echo $ENVIRONMENT  # Should be "development"

# Check apps
python manage.py shell
>>> from django.conf import settings
>>> print('silk' in settings.INSTALLED_APPS)  # Should be True
```

### Silk tables missing?
```bash
python manage.py migrate silk
```

### System checks failing?
```bash
# If deploying and seeing errors about Silk:
export ENVIRONMENT=production
python manage.py check --deploy
# Should show no errors about development tools
```

## Security Notes

1. **Never deploy with `ENVIRONMENT=development`**
   - System checks will catch this
   - Railway/production should use `ENVIRONMENT=production`

2. **Silk stores all requests in database**
   - Only for development
   - Clear regularly: `python manage.py silk_clear_request_log`

3. **Multiple safety layers**
   - Even if you forget to set `ENVIRONMENT`, Railway detection triggers production mode
   - `python manage.py check --deploy` catches misconfigurations

## Next Steps

1. Update `locustfile.py` with your actual book/chapter slugs
2. Run baseline profiling with Silk
3. Run load tests with Locust
4. Compare against Day 16-17 success criteria
5. Deploy confidently knowing tools auto-disable

---

**Questions?** See [DEVELOPMENT_TOOLS_SETUP.md](DEVELOPMENT_TOOLS_SETUP.md) for detailed documentation.
