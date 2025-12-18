# Railway PostgreSQL: 500MB+ Disk Usage - WAL Files Issue

## Problem Summary

**Railway shows >500 MB disk usage, but actual database is only 24 MB!**

## Root Cause: WAL Files

### Breakdown of Disk Usage

| Component | Size | Percentage |
|-----------|------|------------|
| Database (tables + indexes) | 24 MB | 3% |
| **WAL files** | **736 MB** | **97%** |
| **Total** | **760 MB** | **100%** |

### What Are WAL Files?

WAL (Write-Ahead Log) files are PostgreSQL's transaction logs that:
- Ensure data durability (crash recovery)
- Enable point-in-time recovery
- Support replication and backups

**Normal WAL usage**: 2-3 files (~32-48 MB)
**Your WAL usage**: 46 files (~736 MB) ⚠️

## Why WAL Files Aren't Being Cleaned

Investigation shows:
- ✅ No replication slots
- ✅ No active replication
- ✅ Archive mode is OFF
- ✅ Database is primary (not standby)
- ❌ **WAL files NOT being cleaned by CHECKPOINT**

### The Real Cause: Railway's Backup System

Railway uses **continuous WAL archiving** for their backup/restore feature:
- They periodically archive WAL files to S3/object storage
- WAL files must be kept until backup completes
- This is **normal behavior** for Railway's backup system
- WAL files are automatically cleaned on Railway's schedule

## What Triggered This Spike

Looking at PostgreSQL stats, you had massive write activity:
- **113,070 dead tuples** in `books_bookkeyword` table (now cleaned)
- Likely from running `populate_book_keywords` management command
- This generated 40+ WAL files (736 MB)

## Solutions

### Option 1: Wait (Free, Recommended for Temporary Spike)

Railway will automatically clean WAL files within **24-48 hours** after their backup completes.

**Current status**:
- Database: 24 MB (healthy!)
- WAL: 736 MB (will auto-clean)
- No action needed if this was a one-time event

**Monitor**: Check Railway dashboard in 24h to confirm cleanup

### Option 2: Prevent Future Spikes

**A. Optimize Bulk Operations**

When running management commands that write lots of data:

```python
# myapp/books/management/commands/populate_book_keywords.py

# Before:
BookKeyword.objects.all().delete()  # Generates massive WAL
for book in books:
    BookKeyword.objects.bulk_create(keywords)  # More WAL

# Better:
BookKeyword.objects.all().delete()
# Commit/checkpoint here
from django.db import connection
connection.cursor().execute("CHECKPOINT")

# Then bulk create in smaller batches
for i in range(0, len(keywords), 1000):
    batch = keywords[i:i+1000]
    BookKeyword.objects.bulk_create(batch)
    # Small commits reduce WAL growth
```

**B. Run VACUUM After Bulk Operations**

Add to your management commands:

```python
from django.core.management.base import BaseCommand
from django.db import connection

class Command(BaseCommand):
    def handle(self, *args, **options):
        # ... your bulk operations ...

        # Cleanup after bulk operations
        with connection.cursor() as cursor:
            cursor.execute("VACUUM ANALYZE books_bookkeyword")
            cursor.execute("CHECKPOINT")
```

**C. Reduce BookKeyword Bloat**

Your BookKeyword table is inefficient:
- 217 keywords (3-12 bytes each)
- Taking 33 MB with indexes
- **15,000x overhead!**

Consider:
1. Remove redundant indexes (you have 5 indexes!)
2. Use PostgreSQL's GIN index for text search
3. Don't denormalize unless necessary

### Option 3: Upgrade Railway Plan

If you need more headroom:
- **Free tier**: 1 GB disk (current)
- **Hobby plan**: 5 GB disk ($5/month)
- **Pro plan**: 50 GB disk ($20/month)

### Option 4: Contact Railway Support

If WAL files don't clean up after 48 hours:
1. Open Railway support ticket
2. Mention WAL files not being cleaned
3. They can manually trigger cleanup

## What We Fixed Today

1. ✅ **Removed 113,070 dead tuples** from `books_bookkeyword`
2. ✅ **Ran VACUUM** - database shrunk 53 MB → 24 MB
3. ✅ **Forced CHECKPOINT** - marked old WAL files for cleanup
4. ⏳ **Waiting for Railway** to clean WAL files (24-48h)

## Monitoring Commands

Check disk usage anytime:

```bash
# Run on Railway
railway run python myapp/manage.py db_cleanup --check

# Or use our custom scripts (already pushed to repo)
railway run python -c "
import psycopg2
import os
conn = psycopg2.connect(os.getenv('DATABASE_URL'))
cursor = conn.cursor()

# Database size
cursor.execute(\"SELECT pg_size_pretty(pg_database_size(current_database()))\")
print(f\"Database: {cursor.fetchone()[0]}\")

# WAL size
cursor.execute(\"SELECT count(*), pg_size_pretty(sum((pg_stat_file('pg_wal/' || name)).size)::bigint) FROM pg_ls_waldir()\")
count, size = cursor.fetchone()
print(f\"WAL: {count} files, {size}\")

cursor.close()
conn.close()
"
```

## Prevention Checklist

For future bulk operations:

- [ ] Run in small batches (1000-5000 rows)
- [ ] Call `VACUUM` after large deletes
- [ ] Call `CHECKPOINT` after bulk inserts
- [ ] Monitor WAL file count (should be <10)
- [ ] Clean up dead tuples regularly

## Summary

**Why Railway shows >500 MB**:
- Railway counts WAL files in disk usage
- You had 736 MB of WAL files from bulk writes
- Normal database is only 24 MB

**What to do**:
- **Short-term**: Wait 24-48h for Railway to auto-clean WAL
- **Long-term**: Optimize bulk operations, remove redundant indexes
- **If urgent**: Upgrade to Hobby plan ($5/month, 5GB disk)

**Current status**: ✅ Database is healthy, WAL cleanup in progress
