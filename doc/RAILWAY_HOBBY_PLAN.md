# Railway Deployment - Hobby Plan Guide

This guide shows how to deploy the webnovel application on Railway's **Hobby Plan ($5/month)** with optimized resource usage.

## Why Hobby Plan?

- ✅ **Cost-effective**: $5/month vs $20/month Pro plan
- ✅ **Sufficient for early stage**: 500 execution hours/month
- ✅ **Includes PostgreSQL and Redis**: Database plugins don't count toward execution hours
- ✅ **Easy upgrade path**: Can upgrade to Pro when traffic grows

## Hobby Plan Limitations

| Resource | Limit | Your Usage |
|----------|-------|------------|
| Execution Hours | 500/month | 720 (1 service × 24/7) |
| Services | Up to 20 | 3 (Web, PostgreSQL, Redis) |
| Memory | 512MB-8GB | ~1GB recommended |

**Strategy**: Run all services (Django + Celery) in a **single web service** to stay within 500 hours.

## Architecture for Hobby Plan

```
┌─────────────────────────────────────┐
│  Railway Web Service (720h/month)   │
│  ┌───────────────────────────────┐  │
│  │ Gunicorn (Django)             │  │
│  │ - Serves HTTP requests        │  │
│  │ - 1-2 workers                 │  │
│  └───────────────────────────────┘  │
│  ┌───────────────────────────────┐  │
│  │ Celery Worker (background)    │  │
│  │ - Processes async tasks       │  │
│  │ - Optional: disable if unused │  │
│  └───────────────────────────────┘  │
│  ┌───────────────────────────────┐  │
│  │ Celery Beat (background)      │  │
│  │ - Schedules periodic tasks    │  │
│  │ - Optional: disable if unused │  │
│  └───────────────────────────────┘  │
└─────────────────────────────────────┘
         ↓                   ↓
┌─────────────────┐  ┌──────────────┐
│  PostgreSQL     │  │    Redis     │
│  (Plugin - 0h)  │  │ (Plugin - 0h)│
└─────────────────┘  └──────────────┘
```

**Key**: Database plugins don't count toward 500-hour limit!

## Deployment Steps

### Step 1: Create Railway Project

1. Go to https://railway.app/new
2. Click "Deploy from GitHub repo"
3. Select your repository
4. Railway creates a web service automatically

### Step 2: Add PostgreSQL

1. Click "New" → "Database" → "Add PostgreSQL"
2. Railway auto-provides `DATABASE_URL`
3. **Cost**: Free (included in Hobby plan)

### Step 3: Add Redis

1. Click "New" → "Database" → "Add Redis"
2. Railway auto-provides `REDIS_URL`
3. **Cost**: Free (included in Hobby plan)

### Step 4: Configure Web Service

**Build Settings:**
- **Build Command**: `pip install -r requirements/production.txt`
- **Start Command**: `bash scripts/start-web-hobby.sh`

**Environment Variables:**
```bash
# Core Django
ENVIRONMENT=production
DJANGO_DEBUG=False
DJANGO_SECRET_KEY=your-super-secret-key-here-at-least-50-chars-long
DJANGO_ALLOWED_HOSTS=*.railway.app

# Worker settings
WEB_CONCURRENCY=1
ENABLE_CELERY=false
ENABLE_CELERY_BEAT=false

# Database and Redis (auto-provided by Railway)
DATABASE_URL=${{Postgres.DATABASE_URL}}
REDIS_URL=${{Redis.REDIS_URL}}
CELERY_BROKER_URL=${{Redis.REDIS_URL}}
CELERY_RESULT_BACKEND=${{Redis.REDIS_URL}}
```

**Resource Allocation:**
- **Memory**: 1GB (recommended for combined services)
- **CPU**: Shared (default)

### Step 5: Deploy

```bash
# Railway auto-deploys on push to main
git push origin main

# Or trigger manual deployment in Railway dashboard
```

### Step 6: Initialize Database

```bash
# Using Railway CLI
railway run python myapp/manage.py migrate
railway run python myapp/manage.py createsuperuser

# Or using Railway web shell (Settings → Service → Shell)
```

## Configuration Options

### Option A: Web Only (No Background Tasks) - Recommended to Start

**Best for**: Early stage, low traffic, no scheduled tasks needed

```bash
ENABLE_CELERY=false
ENABLE_CELERY_BEAT=false
WEB_CONCURRENCY=1
```

**Pros**:
- Simplest setup
- Lowest memory usage (~512MB)
- Fastest startup
- Most stable

**Cons**:
- No background task processing
- No scheduled tasks (stats updates, etc.)

**When to use**: Initial launch, testing, low traffic

---

### Option B: Web + Celery Worker (Background Tasks)

**Best for**: Need async task processing, but no scheduled tasks

```bash
ENABLE_CELERY=true
ENABLE_CELERY_BEAT=false
WEB_CONCURRENCY=1
```

**Pros**:
- Can process background tasks
- Async operations work
- Better UX for long-running tasks

**Cons**:
- Higher memory usage (~768MB)
- No scheduled tasks

**When to use**: Users triggering translations, exports, etc.

---

### Option C: Web + Celery Worker + Celery Beat (Full Features)

**Best for**: Need both background tasks and scheduled tasks

```bash
ENABLE_CELERY=true
ENABLE_CELERY_BEAT=true
WEB_CONCURRENCY=1
```

**Pros**:
- Full functionality
- Scheduled stats updates work
- Periodic cleanup tasks run

**Cons**:
- Highest memory usage (~1GB)
- Most complex
- If web restarts, all services restart

**When to use**: Production with active users and scheduled tasks needed

## Cost Analysis

### Hobby Plan Breakdown

| Service | Execution Hours | Cost |
|---------|----------------|------|
| Web (combined) | 720h/month | $5/month |
| PostgreSQL | N/A (plugin) | $0 |
| Redis | N/A (plugin) | $0 |
| **TOTAL** | **720h/month** | **$5/month** |

**Note**: 720 hours exceeds 500-hour limit, but Railway charges based on resource usage, not strict cutoff. Actual cost: ~$5-8/month depending on usage.

### Pro Plan Comparison

| Service | Cost | Your Need |
|---------|------|-----------|
| Pro Plan | $20/month | Unlimited hours |
| Multi-service | 3,600h/month | 5 separate services |

**When to upgrade**: When traffic consistently exceeds 15-20 concurrent users or you need advanced observability.

## Performance Expectations

### Single Instance Capacity (from load testing)

Based on your load testing report:

| Metric | Capacity |
|--------|----------|
| Sustained RPS | 15-16 req/s |
| Daily page views | ~1.1M/day (theoretical) |
| Realistic daily users | 5,000-10,000 users |
| Concurrent users | 10-15 comfortable |

**Reality check**: Early stage apps rarely need more than this.

### When You'll Outgrow Hobby Plan

Upgrade to Pro when:
- [ ] Traffic consistently exceeds 20 concurrent users
- [ ] You're serving 50,000+ daily active users
- [ ] Database queries start timing out
- [ ] You need separate services for better isolation
- [ ] You're generating revenue and can justify $20/month

**Estimated timeline**: 6-12 months for typical webnovel app

## Monitoring and Optimization

### Check Resource Usage

```bash
# View logs
railway logs --service web

# Check memory usage (in Railway dashboard)
# Settings → Service → Metrics

# Check execution hours
# Project Settings → Usage
```

### Reduce Memory Usage

If hitting memory limits:

1. **Reduce workers**:
   ```bash
   WEB_CONCURRENCY=1  # Instead of 2
   ```

2. **Disable unused features**:
   ```bash
   ENABLE_CELERY=false  # If not using background tasks
   ```

3. **Optimize Django**:
   ```python
   # settings.py
   CONN_MAX_AGE = 60  # Reduce connection lifetime
   ```

## Scaling Strategy

### Phase 1: Launch (Current) - Hobby Plan
- 1 combined web service
- PostgreSQL plugin
- Redis plugin
- **Cost**: $5-8/month
- **Capacity**: 5,000-10,000 DAU

### Phase 2: Growth - Pro Plan (Separate Services)
- 2-3 web instances (horizontal scaling)
- 1 celery worker instance
- 1 celery beat instance
- PostgreSQL + Redis (larger instances)
- **Cost**: $20-40/month
- **Capacity**: 20,000-50,000 DAU

### Phase 3: Scale - Pro Plan (Optimized)
- 5+ web instances
- 2-3 celery worker instances
- PgBouncer for connection pooling
- Redis cluster
- PostgreSQL read replicas
- **Cost**: $50-100/month
- **Capacity**: 100,000+ DAU

## Troubleshooting

### Issue: Service crashes due to memory

**Solution**: Reduce workers or disable Celery

```bash
WEB_CONCURRENCY=1
ENABLE_CELERY=false
```

### Issue: Background tasks not running

**Solution**: Enable Celery worker

```bash
ENABLE_CELERY=true
```

### Issue: Scheduled tasks not running

**Solution**: Enable Celery beat

```bash
ENABLE_CELERY_BEAT=true
```

### Issue: Exceeding 500 execution hours

**Solution**: Railway doesn't hard-limit at 500h. You'll pay slightly more (~$5-8 total) for 720h.

Alternatively, use sleep schedules:
- Scale down to 0 instances during off-peak hours
- Railway has built-in sleep schedules (Settings → Sleep Schedule)

## Sleep Schedule (Optional Cost Optimization)

If your app doesn't need 24/7 uptime initially:

**Example**: Sleep 8 hours/day (midnight-8am)
- Active: 16 hours/day × 30 days = 480 hours/month ✅
- **Stays within 500-hour limit!**

**Setup**:
1. Railway Dashboard → Web Service → Settings
2. Scroll to "Sleep Schedule"
3. Set: Sleep from 00:00-08:00 (your timezone)

**Pros**: Stay within free tier
**Cons**: Site offline during sleep hours

## Production Checklist

Before going live on Hobby plan:

- [ ] `ENVIRONMENT=production` set
- [ ] `DJANGO_DEBUG=False` set
- [ ] Strong `DJANGO_SECRET_KEY` (50+ chars)
- [ ] `DJANGO_ALLOWED_HOSTS` configured
- [ ] PostgreSQL connected
- [ ] Redis connected
- [ ] Database migrations run
- [ ] Superuser created
- [ ] Static files collected
- [ ] Test site loads correctly
- [ ] Memory usage < 1GB
- [ ] Decide: Enable Celery? (true/false)
- [ ] Decide: Enable Celery Beat? (true/false)

## Generating Strong Secret Key

```python
# Run locally
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Copy output and set as `DJANGO_SECRET_KEY` in Railway.

## Recommended Starting Configuration

For **initial launch**, use this minimal config:

```bash
# Environment
ENVIRONMENT=production
DJANGO_DEBUG=False
DJANGO_SECRET_KEY=<generated-from-above>
DJANGO_ALLOWED_HOSTS=*.railway.app

# Workers (minimal)
WEB_CONCURRENCY=1
ENABLE_CELERY=false
ENABLE_CELERY_BEAT=false

# Database (auto-provided)
DATABASE_URL=${{Postgres.DATABASE_URL}}
REDIS_URL=${{Redis.REDIS_URL}}
```

**Why**: Simplest, most stable, lowest cost. Add Celery later when needed.

## When to Enable Celery

Enable `ENABLE_CELERY=true` when:
- Users need to trigger translations (async task)
- You implement file uploads/processing
- You need email sending without blocking requests
- Any operation takes >5 seconds to complete

Enable `ENABLE_CELERY_BEAT=true` when:
- You need hourly stats updates
- You need daily cleanup tasks
- You implement scheduled notifications
- You need periodic data synchronization

## Summary

**For your current stage**:
- ✅ **Start with Hobby Plan** ($5/month)
- ✅ **3 services**: Web (combined), PostgreSQL, Redis
- ✅ **Disable Celery initially**: Set `ENABLE_CELERY=false`
- ✅ **Enable Celery later**: When you need background tasks
- ✅ **Upgrade to Pro**: When you outgrow (6-12 months)

**Estimated monthly cost**: $5-8/month initially

**You can always upgrade later!** Railway makes it seamless.
