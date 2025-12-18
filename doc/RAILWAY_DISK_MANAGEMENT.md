# Railway Disk Space Management

## Current Issue

**Problem**: PostgreSQL ran out of disk space on Railway
```
FATAL: could not write to file "pg_wal/xlogtemp.29": No space left on device
```

**Cause**: Railway PostgreSQL disk filled up (1GB free tier, 5GB hobby tier)

## Immediate Solutions

### Option 1: Upgrade Railway Plan (Recommended)

1. Go to Railway Dashboard → Project Settings
2. Upgrade from **Free Tier** (1GB) to **Hobby Plan** (5GB disk)
3. Cost: $5/month per service
4. Database will automatically restart with more space

### Option 2: Delete and Recreate Database (DATA LOSS!)

**⚠️ WARNING: This deletes all data!**

1. Go to Railway Dashboard → PostgreSQL Plugin
2. Click "Delete Service"
3. Add new PostgreSQL Plugin
4. Update `DATABASE_URL` environment variable
5. Run migrations: `python manage.py migrate`
6. Reload fixtures/seed data

### Option 3: Manual Cleanup (Temporary Fix)

If you need to keep existing data but can't upgrade immediately:

1. **Connect to Railway PostgreSQL via CLI**:
   ```bash
   # Install Railway CLI if not installed
   npm install -g @railway/cli

   # Login and connect
   railway login
   railway link
   railway run psql $DATABASE_URL
   ```

2. **Check disk usage inside PostgreSQL**:
   ```sql
   SELECT pg_size_pretty(pg_database_size(current_database()));

   SELECT schemaname, tablename,
          pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
   FROM pg_tables
   WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
   ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
   LIMIT 10;
   ```

3. **Run VACUUM to reclaim space**:
   ```sql
   VACUUM FULL ANALYZE;
   ```

## Using the Database Cleanup Command

We've added a management command to help with cleanup:

### Check Database Size
```bash
# On Railway (using Railway CLI)
railway run python myapp/manage.py db_cleanup --check

# Or via SSH if available
python manage.py db_cleanup --check
```

**Output**:
```
=== Database Size Report ===

Total Database Size: 1.2 GB

Top 15 Largest Tables:
----------------------------------------------------------
public.books_chapterview                           450 MB
public.django_celery_beat_periodictask             120 MB
public.books_translationjob                        100 MB
public.books_chapter                                80 MB
...
```

### Run VACUUM
```bash
railway run python myapp/manage.py db_cleanup --vacuum
```

This reclaims disk space from deleted rows without deleting data.

### Clean Old Data
```bash
# Delete data older than 90 days (default)
railway run python myapp/manage.py db_cleanup --clean-old

# Custom retention period (e.g., 30 days)
railway run python myapp/manage.py db_cleanup --clean-old --days=30
```

**What gets cleaned**:
- ✓ Failed/completed translation jobs older than X days
- ✓ Expired Django sessions
- ✗ Chapter views (commented out - enable with caution!)

## Prevention Strategies

### 1. Regular Maintenance (Recommended)

Set up a periodic task to run cleanup:

```python
# In Django admin or management command
from django_celery_beat.models import PeriodicTask, CrontabSchedule

# Run weekly vacuum
schedule, _ = CrontabSchedule.objects.get_or_create(
    minute=0,
    hour=3,
    day_of_week=0,  # Monday
)

PeriodicTask.objects.create(
    crontab=schedule,
    name='Weekly Database Vacuum',
    task='books.tasks.vacuum_database',
)
```

### 2. Data Retention Policies

**Aggressive cleanup** (if running out of space frequently):

```python
# Delete old translation jobs after 30 days
TranslationJob.objects.filter(
    created_at__lt=timezone.now() - timedelta(days=30),
    status__in=['failed', 'completed']
).delete()

# Archive or delete old chapter views after 60 days
ChapterView.objects.filter(
    viewed_at__lt=timezone.now() - timedelta(days=60)
).delete()
```

### 3. Optimize Indexes

Large indexes can consume significant space:

```sql
-- Check index sizes
SELECT
    tablename,
    indexname,
    pg_size_pretty(pg_relation_size(indexrelid)) AS index_size
FROM pg_indexes
JOIN pg_class ON indexrelid = pg_class.oid
WHERE schemaname = 'public'
ORDER BY pg_relation_size(indexrelid) DESC
LIMIT 10;

-- Drop unused indexes (be careful!)
-- Only drop if you're sure they're not needed
DROP INDEX IF EXISTS index_name;
```

### 4. Archive Old Data

Instead of deleting, archive to cheaper storage:

```python
# Export old data to CSV/JSON
from django.core.serializers import serialize

old_jobs = TranslationJob.objects.filter(created_at__lt=cutoff_date)
data = serialize('json', old_jobs)

# Upload to S3/cloud storage
with open('archive.json', 'w') as f:
    f.write(data)

# Then delete from database
old_jobs.delete()
```

## Monitoring Disk Usage

### Railway Dashboard

1. Go to PostgreSQL service in Railway
2. Click **Metrics** tab
3. Monitor **Disk Usage** graph
4. Set up alerts when usage > 80%

### Add Monitoring to Application

```python
# myapp/management/commands/disk_alert.py
from django.core.management.base import BaseCommand
from django.db import connection

class Command(BaseCommand):
    def handle(self, *args, **options):
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT pg_database_size(current_database()) as size_bytes
            """)
            size_bytes = cursor.fetchone()[0]
            size_gb = size_bytes / (1024**3)

            # Alert if > 4GB on hobby plan (80% of 5GB)
            if size_gb > 4.0:
                # Send alert via email/Slack/etc
                print(f"WARNING: Database at {size_gb:.2f}GB")
```

Run periodically via Celery Beat.

## Emergency Recovery

If database won't start due to full disk:

1. **Contact Railway Support**:
   - Railway can temporarily increase disk quota
   - Support usually responds within hours

2. **Upgrade Plan Immediately**:
   - Even during downtime, upgrading gives more space
   - Database should auto-recover once space is available

3. **Restore from Backup** (if available):
   - Railway Pro plan includes automated backups
   - Free/Hobby: You need manual backups

## Backup Strategy (Important!)

Railway free/hobby tier **does not include automatic backups**. You MUST set up backups:

```bash
# Manual backup via Railway CLI
railway run pg_dump $DATABASE_URL > backup_$(date +%Y%m%d).sql

# Automated backup script (run daily)
#!/bin/bash
railway run pg_dump $DATABASE_URL | gzip > backups/backup_$(date +%Y%m%d).sql.gz

# Upload to S3 or other storage
aws s3 cp backups/backup_$(date +%Y%m%d).sql.gz s3://my-backups/
```

## Summary

**Immediate Actions**:
1. ✅ Upgrade to Railway Hobby Plan ($5/month, 5GB disk)
2. ✅ Run `db_cleanup --check` to see what's using space
3. ✅ Run `db_cleanup --vacuum` to reclaim space
4. ✅ Set up automated backups

**Long-term**:
1. ✅ Implement data retention policies
2. ✅ Monitor disk usage regularly
3. ✅ Archive old data instead of keeping forever
4. ✅ Consider upgrading to Pro plan if growth continues

**Current Limits**:
- Free Tier: 1GB disk (likely current plan)
- Hobby: 5GB disk, $5/month
- Pro: 50GB disk, $20/month
- Unlimited: Custom pricing
