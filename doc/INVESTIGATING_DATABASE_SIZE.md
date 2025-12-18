# Investigating Database Size Issues

## Problem Summary

- **Text data**: 1.4 MB (100 chapters)
- **Database size**: 500 MB
- **Ratio**: **357x larger than expected!**

## Why This Happens

### 1. ViewEvent Records (Most Likely Culprit)

Every page view creates a `ViewEvent` with:
- `user_agent`: 1,000-2,000 bytes (full browser string)
- `referrer`: 200-500 bytes (full URL)
- Session tracking metadata
- Timestamps

**Math**:
- 100 chapters × 500 views each = 50,000 ViewEvents
- Each record ≈ 2KB (user_agent + referrer + fields)
- **Data**: 100 MB
- **Indexes** (3 composite indexes): 200-300 MB
- **Total**: **300-400 MB just from ViewEvents!**

### 2. PostgreSQL Overhead

- **TOAST tables**: Text fields > 2KB stored separately
- **Indexes**: 2-5x the size of data
- **Dead tuples**: Old row versions not yet vacuumed
- **WAL files**: Write-ahead logs for crash recovery

### 3. Django Migrations & System Tables

- Django stores migration history
- Content types, permissions, sessions
- Celery beat schedules

## Investigation Steps

### Step 1: Run Analysis on Railway

```bash
# After the latest deploy completes, run:
railway run python myapp/manage.py analyze_db_bloat
```

**This will show**:
- Total database size
- Table sizes (data + indexes)
- Largest indexes
- Dead tuples (bloat)
- Bytes per row (efficiency)
- TOAST table usage

### Step 2: Check ViewEvent Usage

```bash
railway run python myapp/manage.py optimize_viewevents --analyze
```

**This will show**:
- ViewEvent count
- Storage breakdown (table vs indexes)
- User-agent field size
- Age distribution
- Potential savings

### Step 3: Check General Database Health

```bash
railway run python myapp/manage.py db_cleanup --check
```

**This will show**:
- Database size summary
- Top 15 largest tables
- WAL size

## Quick Fixes

### Option 1: Clean User-Agent Data (Safe, Saves ~50%)

```bash
# Remove user_agent and referrer fields (keeps session_key for analytics)
railway run python myapp/manage.py optimize_viewevents --clean-ua

# Reclaim space
railway run python myapp/manage.py db_cleanup --vacuum
```

**Savings**: 150-250 MB

### Option 2: Delete Old ViewEvents (Data Loss!)

```bash
# Delete events older than 30 days
railway run python myapp/manage.py optimize_viewevents --truncate --days=30

# Reclaim space
railway run python myapp/manage.py db_cleanup --vacuum
```

**Savings**: Depends on how many old events exist

### Option 3: Disable ViewEvent Tracking (Prevent Future Bloat)

Edit `settings.py`:

```python
# Temporarily disable stats tracking
MIDDLEWARE = [
    # ... other middleware
    # "books.middleware.StatsTrackingMiddleware",  # <-- Comment out
]
```

This stops creating new ViewEvents but loses analytics.

## Long-Term Solutions

### Solution 1: Optimize ViewEvent Model

Modify `books/models/stat.py`:

```python
class ViewEvent(TimeStampModel):
    # ...

    # DON'T store full user agent (saves 1-2KB per record!)
    user_agent = models.CharField(
        max_length=200,  # ← Changed from TextField
        null=True,
        blank=True,
    )

    # Or remove entirely and use aggregated data only
    # user_agent = None  # ← Remove field
```

### Solution 2: Archive Old ViewEvents

```python
# Create archive task
from django.core.management.base import BaseCommand
from books.models import ViewEvent
from datetime import timedelta
from django.utils import timezone

class Command(BaseCommand):
    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(days=90)

        # Export to JSON/CSV for archives
        old_events = ViewEvent.objects.filter(viewed_at__lt=cutoff)

        # Save to file/S3
        with open('archive.json', 'w') as f:
            serialize('json', old_events, stream=f)

        # Delete from database
        old_events.delete()
```

### Solution 3: Use Aggregated Stats Only

Instead of keeping every ViewEvent forever:

1. **Aggregate to ChapterStats/BookStats** (daily Celery task)
2. **Delete ViewEvents after aggregation** (keep 7-30 days max)
3. **Save 90% of space**

```python
# In Celery beat schedule
from celery import shared_task
from books.models import ViewEvent, ChapterStats
from datetime import timedelta
from django.utils import timezone

@shared_task
def aggregate_and_cleanup_stats():
    """Aggregate ViewEvents to ChapterStats, then delete old events."""
    # Aggregate (your existing logic)
    aggregate_chapter_stats()

    # Delete events older than 30 days
    cutoff = timezone.now() - timedelta(days=30)
    deleted_count, _ = ViewEvent.objects.filter(viewed_at__lt=cutoff).delete()

    return f"Deleted {deleted_count} old ViewEvents"
```

### Solution 4: Reduce Index Count

Remove unnecessary indexes from `books/models/stat.py`:

```python
class ViewEvent(TimeStampModel):
    class Meta:
        indexes = [
            # Keep only the most important index
            models.Index(fields=["content_type", "object_id", "viewed_at"]),
            # Remove these:
            # models.Index(fields=["viewed_at"]),  # ← Redundant
            # models.Index(fields=["session_key", "viewed_at"]),  # ← Rarely used?
        ]
```

Each removed index saves 50-100 MB!

## Monitoring & Prevention

### Set Up Disk Usage Alerts

```python
# myapp/books/management/commands/check_disk_usage.py
from django.core.management.base import BaseCommand
from django.db import connection

class Command(BaseCommand):
    def handle(self, *args, **options):
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_database_size(current_database())")
            size_bytes = cursor.fetchone()[0]
            size_mb = size_bytes / (1024 ** 2)

            # Alert if > 400MB (80% of 500MB limit)
            if size_mb > 400:
                # Send email/Slack alert
                print(f"WARNING: Database at {size_mb:.0f}MB")
```

Run daily via Celery Beat.

### Automated Cleanup

```python
# In celery beat schedule
from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    'cleanup-old-viewevents': {
        'task': 'books.tasks.cleanup_old_viewevents',
        'schedule': crontab(hour=3, minute=0, day_of_week=1),  # Weekly on Monday 3am
    },
}
```

## Expected Results After Cleanup

| Action | Before | After | Savings |
|--------|--------|-------|---------|
| Clean user_agent | 500 MB | 250 MB | 50% |
| Delete old events (90d) | 500 MB | 200 MB | 60% |
| Both + VACUUM | 500 MB | 150 MB | 70% |

## Railway Commands Cheat Sheet

```bash
# Investigation
railway run python myapp/manage.py analyze_db_bloat
railway run python myapp/manage.py optimize_viewevents --analyze
railway run python myapp/manage.py db_cleanup --check

# Cleanup
railway run python myapp/manage.py optimize_viewevents --clean-ua
railway run python myapp/manage.py optimize_viewevents --truncate --days=30
railway run python myapp/manage.py db_cleanup --vacuum

# Direct PostgreSQL access
railway run psql $DATABASE_URL
# Then run SQL:
# SELECT pg_size_pretty(pg_database_size(current_database()));
# SELECT schemaname, tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename))
# FROM pg_tables WHERE schemaname = 'public' ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

## Summary

**Most Likely Cause**: ViewEvent records with large user_agent fields + multiple indexes

**Quick Win**: Run `optimize_viewevents --clean-ua` to remove user_agent data (saves ~250MB)

**Long-term Fix**: Implement automatic ViewEvent cleanup (delete after 30 days)

**Prevention**: Consider not storing user_agent at all, or aggregating stats and deleting raw events sooner
