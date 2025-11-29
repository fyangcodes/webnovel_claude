# Development Tools Setup Guide

This guide explains how to set up and use Silk and Locust for load testing (Day 16-17 of optimization plan).

## Overview

The project uses two complementary tools for performance testing:

1. **Django Silk**: Request profiling and SQL query analysis (development only)
2. **Locust**: Load testing and stress testing (can run in dev or staging)

Both tools are configured to **NEVER run in production** through multiple safety mechanisms.

## Safety Mechanisms

### 1. Environment-Based Control

The `ENVIRONMENT` variable controls which tools are loaded:

```bash
# Development (.env)
ENVIRONMENT=development  # Enables Silk and Debug Toolbar

# Production (.env.production or Railway)
ENVIRONMENT=production   # Disables all development tools
```

### 2. Conditional Installation

Tools are only added to `INSTALLED_APPS` when `IS_DEVELOPMENT=True`:

```python
# settings.py
IS_DEVELOPMENT = os.getenv("ENVIRONMENT", "production") == "development"

if IS_DEVELOPMENT:
    INSTALLED_APPS += ["silk", "debug_toolbar"]
    MIDDLEWARE.insert(2, "silk.middleware.SilkyMiddleware")
```

### 3. Separate Requirements Files

```bash
# Development
pip install -r requirements/development.txt  # Includes silk, locust

# Production
pip install -r requirements/production.txt   # NO development tools
```

### 4. Django System Checks

Automated checks prevent accidental production deployment:

```bash
python manage.py check --deploy
```

Will show **ERRORS** if:
- `DEBUG=True` in production
- `ENVIRONMENT=development` in production
- Silk or Debug Toolbar in `INSTALLED_APPS` in production
- Default `SECRET_KEY` in production

### 5. URL Protection

Development tool URLs only register when apps are installed:

```python
if "silk" in settings.INSTALLED_APPS:
    urlpatterns += [path("silk/", include("silk.urls"))]
```

## Installation

### Step 1: Install Dependencies

```bash
# Activate virtual environment
source .venv/bin/activate

# Install development dependencies (includes Silk and Locust)
pip install -r requirements/development.txt
```

### Step 2: Configure Environment

Edit `.env` file:

```bash
# MUST be set to "development" for tools to load
ENVIRONMENT=development

# Can be True or False (but ENVIRONMENT is primary control)
DJANGO_DEBUG=True
```

### Step 3: Run Migrations

Silk creates database tables to store profiling data:

```bash
cd myapp
python manage.py migrate
```

### Step 4: Verify Installation

```bash
# Check that development tools are enabled
python manage.py runserver

# You should see:
# 🔧 Development mode: Silk and Debug Toolbar enabled
# 🔧 Silk profiling configured (visit /silk/ to view requests)
```

## Using Django Silk

### Accessing Silk UI

1. Start development server:
   ```bash
   python manage.py runserver
   ```

2. Make some requests to your app:
   ```bash
   # Visit pages in browser or use curl
   curl http://127.0.0.1:8000/en/
   curl http://127.0.0.1:8000/en/fiction/
   curl http://127.0.0.1:8000/en/fiction/b/your-book-slug/
   ```

3. Open Silk UI:
   ```
   http://127.0.0.1:8000/silk/
   ```

### Understanding Silk Interface

**Request List:**
- Shows all HTTP requests
- Columns: URL, time, # queries, request time
- Filter by URL pattern, date, query count

**Request Detail:**
- SQL queries executed (with EXPLAIN)
- Time spent in each layer (view, template, DB)
- Python profiler data (function calls)
- Request/response headers

**Key Metrics:**
- **Query count**: Should be < 50 for most pages
- **Similar queries**: Indicates N+1 problems
- **Duplicate queries**: Indicates missing prefetch
- **Total time**: Should be < 200ms for optimized pages

### Finding N+1 Queries

1. Click on a request in Silk
2. Look at "SQL queries" section
3. Click "Similar queries" tab
4. If you see 10+ identical queries with different IDs → N+1 problem

Example:
```sql
SELECT * FROM books_genre WHERE id = 1  -- Query 1
SELECT * FROM books_genre WHERE id = 2  -- Query 2
SELECT * FROM books_genre WHERE id = 3  -- Query 3
...  -- This is an N+1 problem!
```

### Cleaning Up Silk Data

Silk stores ALL requests in the database. Clean periodically:

```bash
# Delete all profiling data
python manage.py silk_clear_request_log

# Or use Django admin
http://127.0.0.1:8000/admin/silk/
```

## Using Locust for Load Testing

### Creating Test Scenarios

Create `locustfile.py` in project root:

```python
from locust import HttpUser, task, between
import random

class WebNovelReaderUser(HttpUser):
    wait_time = between(1, 3)  # Wait 1-3 seconds between requests
    host = "http://127.0.0.1:8000"

    @task(10)  # Weight: 10 (runs 10x more often than weight=1)
    def browse_homepage(self):
        """Most common action: browse homepage"""
        self.client.get("/en/")

    @task(5)
    def browse_section(self):
        """Browse a section"""
        sections = ['fiction', 'bl', 'gl']
        section = random.choice(sections)
        self.client.get(f"/en/{section}/")

    @task(3)
    def view_book_detail(self):
        """View a book"""
        # Replace with actual book slugs from your database
        self.client.get("/en/fiction/b/test-book/")

    @task(2)
    def read_chapter(self):
        """Read a chapter"""
        self.client.get("/en/fiction/b/test-book/c/chapter-1/")
```

### Running Load Tests

**Method 1: Web UI (Recommended)**

```bash
# Start Locust
locust -f locustfile.py

# Open browser
http://localhost:8089

# Configure:
# - Number of users: 100
# - Spawn rate: 10 (users per second)
# - Host: http://127.0.0.1:8000

# Click "Start swarming"
```

**Method 2: Headless (Command Line)**

```bash
# Run test for 5 minutes with 100 users
locust -f locustfile.py \
  --headless \
  --users 100 \
  --spawn-rate 10 \
  --run-time 5m \
  --html report.html
```

### Interpreting Results

**Key Metrics:**

| Metric | Target (Day 16-17) | Meaning |
|--------|-------------------|---------|
| Homepage p95 | < 200ms | 95% of requests faster than this |
| Book list p95 | < 300ms | Section/category list pages |
| Book detail p95 | < 200ms | Individual book page |
| Failures | 0% | HTTP errors (500, 404, etc.) |

**What p95 means:**
- p50 (median): 50% of requests are faster
- p95: 95% of requests are faster (filters outliers)
- p99: 99% of requests are faster

**Warning Signs:**
- ❌ Failures > 0%: Application errors under load
- ❌ p95 increasing over time: Memory leak or resource exhaustion
- ❌ RPS decreasing over time: Database connection pool exhaustion

### Example Load Test Results

**Good Performance:**
```
Name                  # reqs  # fails  Avg    Min    Max    p50    p95    p99
/en/                   5000   0 (0%)   45ms   12ms   250ms  40ms   120ms  180ms
/en/fiction/           2500   0 (0%)   78ms   20ms   400ms  65ms   200ms  320ms
/en/fiction/b/*/       1500   0 (0%)   92ms   25ms   500ms  80ms   180ms  350ms
```

**Poor Performance (needs optimization):**
```
Name                  # reqs  # fails  Avg    Min    Max    p50    p95    p99
/en/                   5000   12 (0.2%) 450ms  120ms  2500ms 400ms  1200ms 2000ms
/en/fiction/           2500   45 (1.8%) 780ms  200ms  4000ms 650ms  2000ms 3200ms
```

## Day 16-17 Testing Workflow

### Phase 1: Baseline Profiling with Silk

```bash
# 1. Ensure development environment
export ENVIRONMENT=development

# 2. Start server
python manage.py runserver

# 3. Make test requests
curl http://127.0.0.1:8000/en/
curl http://127.0.0.1:8000/en/fiction/
curl http://127.0.0.1:8000/en/fiction/b/your-book-slug/

# 4. Review in Silk
# http://127.0.0.1:8000/silk/
# - Check query count (should be < 50)
# - Look for N+1 patterns
# - Verify cache is being used
```

### Phase 2: Load Testing with Locust

```bash
# 1. Create locustfile.py (see example above)

# 2. Run homepage test (100 concurrent users)
locust -f locustfile.py \
  --headless \
  --users 100 \
  --spawn-rate 10 \
  --run-time 5m \
  --html homepage_test.html

# 3. Check results
# - Homepage p95 < 200ms? ✅
# - No failures? ✅
# - RPS stable? ✅
```

### Phase 3: Identify Bottlenecks

If tests fail:

1. **Use Silk** to find slow queries
   - Look for queries > 50ms
   - Check for N+1 patterns
   - Verify prefetch is working

2. **Check cache hit rates**
   ```bash
   # In Django shell
   python manage.py shell
   ```
   ```python
   from django.core.cache import cache
   from django_redis import get_redis_connection

   r = get_redis_connection("default")
   info = r.info("stats")
   hit_rate = info['keyspace_hits'] / (info['keyspace_hits'] + info['keyspace_misses'])
   print(f"Cache hit rate: {hit_rate:.2%}")  # Should be > 80%
   ```

3. **Check database connection pool**
   ```bash
   # Monitor PostgreSQL connections during load test
   docker exec -it webnovel-db psql -U postgres -c "SELECT count(*) FROM pg_stat_activity;"
   ```

### Phase 4: Fix and Retest

1. Fix issues found in Silk
2. Clear Silk profiling data: `python manage.py silk_clear_request_log`
3. Re-run Locust tests
4. Compare results

## Production Deployment Checklist

Before deploying, verify:

```bash
# 1. Set production environment
export ENVIRONMENT=production
export DJANGO_DEBUG=False

# 2. Run system checks
python manage.py check --deploy

# Expected output: NO errors about Silk or Debug Toolbar

# 3. Verify apps list
python manage.py shell
```

```python
from django.conf import settings
print('silk' in settings.INSTALLED_APPS)  # Should be False
print('debug_toolbar' in settings.INSTALLED_APPS)  # Should be False
print(settings.IS_DEVELOPMENT)  # Should be False
```

## Troubleshooting

### Silk Not Showing Up

```bash
# Check environment
echo $ENVIRONMENT  # Should be "development"

# Check installed apps
python manage.py shell
```
```python
from django.conf import settings
print('silk' in settings.INSTALLED_APPS)  # Should be True
```

### Silk Database Tables Missing

```bash
python manage.py migrate silk
```

### Locust Connection Refused

```bash
# Make sure Django is running on correct port
python manage.py runserver 127.0.0.1:8000

# Update locustfile.py host if needed
host = "http://127.0.0.1:8000"  # Check port number
```

### High Query Count Despite Optimization

1. Disable cache to see real query count:
   ```bash
   # In .env
   DISABLE_CACHE=True
   ```

2. Check if prefetch is working:
   ```python
   # In Django shell
   from books.models import Book
   books = Book.objects.for_list_display('en', 'fiction')[:6]

   # Force evaluation
   list(books)

   # Check query count
   from django.db import connection
   print(len(connection.queries))  # Should be < 15
   ```

## Additional Resources

- [Django Silk Documentation](https://github.com/jazzband/django-silk)
- [Locust Documentation](https://docs.locust.io/)
- [MASTER_OPTIMIZATION_PLAN.md](MASTER_OPTIMIZATION_PLAN.md) - Full optimization roadmap
- [OPTIMIZATION_SUMMARY.md](OPTIMIZATION_SUMMARY.md) - Quick reference

## Summary

**Key Takeaways:**

1. ✅ Silk is for **development profiling** (query analysis, N+1 detection)
2. ✅ Locust is for **load testing** (concurrent users, response times)
3. ✅ Both are **automatically disabled in production** via `ENVIRONMENT=production`
4. ✅ Multiple safety mechanisms prevent accidental production usage
5. ✅ Use `python manage.py check --deploy` before deploying

**Workflow:**
1. Profile with Silk → Find slow queries
2. Fix issues → Re-profile with Silk
3. Load test with Locust → Verify performance at scale
4. Deploy to production → Tools automatically disabled
