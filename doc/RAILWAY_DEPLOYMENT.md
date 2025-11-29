# Railway Multi-Service Deployment Guide

This guide explains how to deploy the webnovel application with all its services (Django, PostgreSQL, Redis, Celery Worker, Celery Beat) to Railway.

## Architecture Overview

The application uses the following services:

1. **Web Service** - Django application (Gunicorn)
2. **Celery Worker** - Background task processor
3. **Celery Beat** - Scheduled task scheduler
4. **PostgreSQL** - Database (Railway Plugin)
5. **Redis** - Cache and message broker (Railway Plugin)

## Prerequisites

- Railway account (https://railway.app)
- Railway CLI installed (optional, but recommended)
- Git repository connected to Railway

## Deployment Steps

### Step 1: Create a New Railway Project

```bash
# Install Railway CLI (if not installed)
npm install -g @railway/cli

# Login to Railway
railway login

# Create new project or link existing
railway init
```

Or use the Railway web dashboard:
1. Go to https://railway.app/new
2. Select "Deploy from GitHub repo"
3. Connect your repository

### Step 2: Add PostgreSQL Database

1. In Railway dashboard, click "New" → "Database" → "Add PostgreSQL"
2. Railway will automatically create a PostgreSQL instance
3. Environment variables are automatically set:
   - `DATABASE_URL` (automatically provided by Railway)

### Step 3: Add Redis

1. In Railway dashboard, click "New" → "Database" → "Add Redis"
2. Railway will automatically create a Redis instance
3. Environment variables are automatically set:
   - `REDIS_URL` (automatically provided by Railway)

### Step 4: Add Web Service (Django)

1. In Railway dashboard, click "New" → "Service" → "GitHub Repo"
2. Select your repository
3. Configure service:
   - **Name**: `web`
   - **Start Command**: `bash scripts/start-web.sh`
   - **Build Command**: `pip install -r requirements/production.txt`

4. Add environment variables (Settings → Variables):
   ```
   ENVIRONMENT=production
   DJANGO_DEBUG=False
   DJANGO_SECRET_KEY=<generate-a-strong-secret-key>
   DJANGO_ALLOWED_HOSTS=*.railway.app
   WEB_CONCURRENCY=2
   PORT=8000
   ```

5. Connect to PostgreSQL and Redis:
   - Railway will automatically link DATABASE_URL and REDIS_URL

### Step 5: Add Celery Worker Service

1. In Railway dashboard, click "New" → "Empty Service"
2. Connect to your GitHub repo (same repo as web)
3. Configure service:
   - **Name**: `celery-worker`
   - **Start Command**: `bash scripts/start-celery-worker.sh`
   - **Build Command**: `pip install -r requirements/production.txt`

4. Add environment variables:
   ```
   ENVIRONMENT=production
   DJANGO_DEBUG=False
   DJANGO_SECRET_KEY=<same-as-web-service>
   CELERY_WORKER_CONCURRENCY=2
   ```

5. Connect to PostgreSQL and Redis (same as web service)

### Step 6: Add Celery Beat Service

1. In Railway dashboard, click "New" → "Empty Service"
2. Connect to your GitHub repo (same repo as web)
3. Configure service:
   - **Name**: `celery-beat`
   - **Start Command**: `bash scripts/start-celery-beat.sh`
   - **Build Command**: `pip install -r requirements/production.txt`

4. Add environment variables:
   ```
   ENVIRONMENT=production
   DJANGO_DEBUG=False
   DJANGO_SECRET_KEY=<same-as-web-service>
   ```

5. Connect to PostgreSQL and Redis (same as web service)

### Step 7: Configure Environment Variables (All Services)

Add these to **all three services** (web, celery-worker, celery-beat):

```bash
# Django Core
ENVIRONMENT=production
DJANGO_DEBUG=False
DJANGO_SECRET_KEY=<generate-strong-secret-key>
DJANGO_ALLOWED_HOSTS=*.railway.app,yourdomain.com

# Database (automatically provided by Railway when linked)
DATABASE_URL=<provided-by-railway>

# Redis (automatically provided by Railway when linked)
REDIS_URL=<provided-by-railway>

# Celery
CELERY_BROKER_URL=$REDIS_URL
CELERY_RESULT_BACKEND=$REDIS_URL

# Optional: Featured content configuration
FEATURED_BOOK_IDS=1,2,3
FEATURED_GENRE_IDS=1,2,3,4

# Optional: AWS S3 (if using)
# AWS_ACCESS_KEY_ID=your-access-key
# AWS_SECRET_ACCESS_KEY=your-secret-key
# AWS_STORAGE_BUCKET_NAME=your-bucket-name
# AWS_S3_REGION_NAME=us-east-1
```

### Step 8: Deploy

Railway will automatically deploy when you push to your main branch.

```bash
# Push to main branch to trigger deployment
git push origin main
```

Or manually trigger deployment in Railway dashboard:
1. Go to each service
2. Click "Deploy" → "Deploy Latest Commit"

### Step 9: Run Initial Setup Commands

After deployment, run these commands in the web service:

```bash
# Open Railway shell for web service
railway run --service web bash

# Or use Railway CLI
railway shell

# Run migrations
python myapp/manage.py migrate

# Create superuser
python myapp/manage.py createsuperuser

# (Optional) Load sample data
python myapp/manage.py seed_taxonomy
```

## Service Configuration Details

### Web Service Configuration

**Purpose**: Serves HTTP requests for the Django application

**Start Command**: `bash scripts/start-web.sh`

**What it does**:
- Collects static files
- Runs database migrations
- Compiles translation messages
- Starts Gunicorn WSGI server

**Scaling**: Can be scaled horizontally (multiple instances)

### Celery Worker Configuration

**Purpose**: Processes background tasks (stats updates, async operations)

**Start Command**: `bash scripts/start-celery-worker.sh`

**What it does**:
- Waits for database to be ready
- Starts Celery worker process
- Processes tasks from Redis queue

**Scaling**: Can be scaled horizontally (multiple workers)

**Configuration**:
- Concurrency: 2 workers (adjust via `CELERY_WORKER_CONCURRENCY`)
- Max tasks per child: 100 (prevents memory leaks)
- Time limit: 300s per task

### Celery Beat Configuration

**Purpose**: Schedules periodic tasks (hourly stats updates, daily cleanup)

**Start Command**: `bash scripts/start-celery-beat.sh`

**What it does**:
- Waits for database to be ready
- Starts Celery Beat scheduler
- Uses DatabaseScheduler (django-celery-beat)

**Scaling**: Should only run **ONE instance** (do not scale)

**Important**: Only run one Celery Beat instance to avoid duplicate task execution.

## Environment Variable Reference

### Required for All Services

| Variable | Description | Example |
|----------|-------------|---------|
| `ENVIRONMENT` | Environment mode | `production` |
| `DJANGO_DEBUG` | Debug mode (should be False) | `False` |
| `DJANGO_SECRET_KEY` | Django secret key | `<random-50-char-string>` |
| `DATABASE_URL` | PostgreSQL connection | Auto-provided by Railway |
| `REDIS_URL` | Redis connection | Auto-provided by Railway |

### Optional Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `DJANGO_ALLOWED_HOSTS` | Comma-separated hosts | `*.railway.app` |
| `WEB_CONCURRENCY` | Gunicorn workers | `2` |
| `CELERY_WORKER_CONCURRENCY` | Celery worker processes | `2` |
| `FEATURED_BOOK_IDS` | Featured book IDs | None |
| `FEATURED_GENRE_IDS` | Featured genre IDs | None |

## Monitoring and Debugging

### View Logs

```bash
# Web service logs
railway logs --service web

# Celery worker logs
railway logs --service celery-worker

# Celery beat logs
railway logs --service celery-beat

# All services
railway logs
```

### Check Service Health

1. **Web Service**: Visit your Railway domain (e.g., https://your-app.railway.app)
2. **Celery Worker**: Check logs for "ready" message
3. **Celery Beat**: Check logs for "Scheduler: Sending due task" messages

### Common Issues

#### Issue: Web service fails to start

**Solution**: Check environment variables are set correctly

```bash
railway logs --service web
# Look for missing environment variables or migration errors
```

#### Issue: Celery worker can't connect to Redis

**Solution**: Ensure Redis service is linked to celery-worker service

1. Go to celery-worker service settings
2. Click "Variables" → "Reference Variables"
3. Link `REDIS_URL` from Redis service

#### Issue: Database migrations fail

**Solution**: Run migrations manually

```bash
railway run --service web python myapp/manage.py migrate
```

#### Issue: Static files not loading

**Solution**: Ensure WhiteNoise is enabled and collectstatic runs

```bash
# Check if collectstatic ran in logs
railway logs --service web | grep collectstatic

# Force collectstatic
railway run --service web python myapp/manage.py collectstatic --noinput
```

## Updating the Application

### Push to Deploy

Railway automatically deploys on push to main:

```bash
git add .
git commit -m "Update application"
git push origin main
```

### Manual Deployment

1. Go to Railway dashboard
2. Select service
3. Click "Deploy" → "Deploy Latest Commit"

### Running Migrations After Update

```bash
# Migrations run automatically via start-web.sh
# But you can run manually if needed:
railway run --service web python myapp/manage.py migrate
```

## Production Checklist

Before going live, ensure:

- [ ] `ENVIRONMENT=production` set on all services
- [ ] `DJANGO_DEBUG=False` set on all services
- [ ] Strong `DJANGO_SECRET_KEY` generated and set
- [ ] `DJANGO_ALLOWED_HOSTS` includes your domain
- [ ] PostgreSQL database is provisioned
- [ ] Redis is provisioned
- [ ] All services are connected to PostgreSQL and Redis
- [ ] Database migrations have run
- [ ] Superuser account created
- [ ] Static files collected
- [ ] Custom domain configured (if applicable)
- [ ] HTTPS enforced
- [ ] Only ONE celery-beat instance running

## Custom Domain Setup

1. In Railway dashboard, go to web service
2. Click "Settings" → "Domains"
3. Click "Add Domain"
4. Follow Railway's instructions to configure DNS

Update `DJANGO_ALLOWED_HOSTS`:
```
DJANGO_ALLOWED_HOSTS=*.railway.app,yourdomain.com,www.yourdomain.com
```

## Scaling Recommendations

### Free Tier
- Web: 1 instance
- Celery Worker: 1 instance
- Celery Beat: 1 instance

### Production
- Web: 2-4 instances (horizontal scaling)
- Celery Worker: 2-4 instances (based on load)
- Celery Beat: **1 instance only** (never scale)

## Cost Optimization

- Use Railway's free tier for testing
- Monitor usage in Railway dashboard
- Scale down celery workers during low-traffic periods
- Use Redis for caching to reduce database queries

## Rollback Strategy

### Rollback to Previous Deployment

1. Go to Railway dashboard → Service → Deployments
2. Find previous successful deployment
3. Click "..." → "Redeploy"

### Rollback via Git

```bash
# Revert to previous commit
git revert HEAD
git push origin main
```

## Next Steps

After deployment:

1. **Test the application**: Visit your Railway domain
2. **Create admin account**: `railway run --service web python myapp/manage.py createsuperuser`
3. **Load initial data**: `railway run --service web python myapp/manage.py seed_taxonomy`
4. **Configure periodic tasks**: Go to Django admin → Periodic tasks
5. **Monitor logs**: `railway logs`

## Support

- Railway Docs: https://docs.railway.app
- Django Deployment: https://docs.djangoproject.com/en/stable/howto/deployment/
- Celery Docs: https://docs.celeryproject.org

## Alternative: Single-Service Deployment (Not Recommended)

If you want to run everything in a single Railway service (simpler but less scalable):

1. Use the old `start.sh` script
2. Modify it to start all processes:

```bash
#!/bin/bash
cd myapp
python manage.py collectstatic --noinput
python manage.py migrate

# Start celery worker in background
celery -A myapp worker --loglevel=info --concurrency=2 &

# Start celery beat in background
celery -A myapp beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler &

# Start web server
exec gunicorn myapp.wsgi --bind 0.0.0.0:$PORT
```

**Note**: This approach is not recommended for production as:
- All processes restart when one fails
- Cannot scale services independently
- Higher memory usage per instance
- More difficult to debug issues
