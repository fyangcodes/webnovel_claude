# Railway Hobby Plan - Quick Start Guide

This guide gets you deployed on Railway Hobby Plan in 15 minutes.

## What You're Deploying

**Architecture**: All-in-one service (Web + Celery + Database)

```
┌───────────────────────────────────────┐
│   Railway Web Service (720h/month)    │
│   ┌─────────────────────────────────┐ │
│   │ Gunicorn (Django web server)    │ │
│   │ Celery Worker (optional)        │ │
│   │ Celery Beat (optional)          │ │
│   └─────────────────────────────────┘ │
└───────────────────────────────────────┘
           ↓                    ↓
┌──────────────────┐  ┌─────────────────┐
│  PostgreSQL      │  │     Redis       │
│  (Plugin - FREE) │  │  (Plugin - FREE)│
└──────────────────┘  └─────────────────┘
```

**Cost**: $5-8/month

## Step-by-Step Deployment

### Step 1: Prepare Your Code

```bash
# Ensure you're on the right branch
git checkout feature/analytics-stats

# Commit any pending changes
git add .
git commit -m "Prepare for Railway deployment"
git push origin feature/analytics-stats

# Merge to main
git checkout main
git merge feature/analytics-stats
git push origin main
```

### Step 2: Create Railway Project

1. Go to https://railway.app/new
2. Click **"Deploy from GitHub repo"**
3. Select your `webnovel_claude` repository
4. Railway will create a web service automatically

### Step 3: Add PostgreSQL Database

1. In Railway dashboard, click **"New"** → **"Database"** → **"Add PostgreSQL"**
2. Railway automatically sets `DATABASE_URL` environment variable
3. **Cost**: FREE (included in Hobby plan)

### Step 4: Add Redis

1. Click **"New"** → **"Database"** → **"Add Redis"**
2. Railway automatically sets `REDIS_URL` environment variable
3. **Cost**: FREE (included in Hobby plan)

### Step 5: Configure Web Service

Click on your **Web service**, then go to **Settings**:

#### Build Settings

- **Build Command**: `pip install -r requirements/production.txt`
- **Start Command**: `bash scripts/start-web-hobby.sh`

#### Environment Variables

Click **"Variables"** tab and add:

```bash
# Django Core
ENVIRONMENT=production
DJANGO_DEBUG=False
DJANGO_SECRET_KEY=<generate-this-below>
DJANGO_ALLOWED_HOSTS=*.railway.app

# Web Server
WEB_CONCURRENCY=1
PORT=8000

# Celery (choose your configuration)
ENABLE_CELERY=false
ENABLE_CELERY_BEAT=false

# Database (auto-linked by Railway)
DATABASE_URL=${{Postgres.DATABASE_URL}}
REDIS_URL=${{Redis.REDIS_URL}}
CELERY_BROKER_URL=${{Redis.REDIS_URL}}
CELERY_RESULT_BACKEND=${{Redis.REDIS_URL}}
```

#### Generate Django Secret Key

Run this locally to generate a secure key:

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Copy the output and paste it as `DJANGO_SECRET_KEY` in Railway.

### Step 6: Link Database Services

Railway should auto-link PostgreSQL and Redis. Verify:

1. Go to **Web Service** → **Variables**
2. You should see:
   - `DATABASE_URL` (linked from PostgreSQL)
   - `REDIS_URL` (linked from Redis)

If not, manually add references:
1. Click **"New Variable"** → **"Reference"**
2. Select PostgreSQL → `DATABASE_URL`
3. Repeat for Redis → `REDIS_URL`

### Step 7: Deploy

Railway auto-deploys when you push to `main`:

```bash
# Already done in Step 1
git push origin main
```

Or trigger manual deployment:
1. Go to **Web Service** → **Deployments**
2. Click **"Deploy"**

### Step 8: Monitor Deployment

1. Go to **Web Service** → **Deployments**
2. Click on the latest deployment
3. Watch the **Logs** tab for:
   ```
   Collecting static files... ✓
   Running database migrations... ✓
   Starting Gunicorn web server... ✓
   ```

### Step 9: Initialize Database

After deployment succeeds, create your admin user:

#### Option A: Using Railway CLI

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login
railway login

# Link to your project
railway link

# Create superuser
railway run python myapp/manage.py createsuperuser
```

#### Option B: Using Railway Web Shell

1. Go to **Web Service** → **Settings** → **Service**
2. Scroll to **"Shell"**
3. Click **"Open Shell"**
4. Run:
   ```bash
   cd myapp
   python manage.py createsuperuser
   ```

### Step 10: Test Your Site

1. Go to **Web Service** → **Settings** → **Domains**
2. Copy your Railway domain (e.g., `your-app.railway.app`)
3. Visit: `https://your-app.railway.app/en/fiction/`
4. You should see your homepage!

## Configuration Options

### Option A: Web Only (Recommended for Launch)

**Best for**: Initial launch, low traffic, minimal complexity

```bash
ENABLE_CELERY=false
ENABLE_CELERY_BEAT=false
WEB_CONCURRENCY=1
```

**Memory usage**: ~512MB
**What works**: All web pages, browsing, search
**What doesn't work**: Background tasks, scheduled tasks

### Option B: Web + Background Tasks

**Best for**: Need async operations (translations, exports, etc.)

```bash
ENABLE_CELERY=true
ENABLE_CELERY_BEAT=false
WEB_CONCURRENCY=1
CELERY_WORKER_CONCURRENCY=1
```

**Memory usage**: ~768MB
**What works**: Web + background task processing
**What doesn't work**: Scheduled tasks

### Option C: Full Features

**Best for**: Production with scheduled tasks (stats updates, cleanup)

```bash
ENABLE_CELERY=true
ENABLE_CELERY_BEAT=true
WEB_CONCURRENCY=1
CELERY_WORKER_CONCURRENCY=1
```

**Memory usage**: ~1GB
**What works**: Everything!

## Troubleshooting

### Deployment fails with "Module not found"

**Fix**: Ensure `requirements/production.txt` includes all dependencies

```bash
# Build command should be:
pip install -r requirements/production.txt
```

### Can't connect to database

**Fix**: Verify DATABASE_URL is linked

1. Go to **Web Service** → **Variables**
2. Check `DATABASE_URL` exists and shows PostgreSQL icon
3. If missing, add reference to Postgres service

### Celery not starting

**Check logs**:
```bash
railway logs --service web | grep -i celery
```

**Common issues**:
- `ENABLE_CELERY` not set to `"true"` (must be string "true")
- Redis not linked (`REDIS_URL` missing)
- Wrong working directory

### Static files not loading

**Fix**: Check collectstatic ran successfully

```bash
railway logs --service web | grep collectstatic
```

Should see:
```
Collecting static files...
X static files copied to '/app/staticfiles'
```

### Out of memory errors

**Fix**: Reduce workers or disable Celery

```bash
WEB_CONCURRENCY=1
ENABLE_CELERY=false
```

Or increase memory in Railway:
1. **Web Service** → **Settings** → **Resources**
2. Increase memory limit

## Monitoring

### View Logs

```bash
# Real-time logs
railway logs --service web

# Filter for errors
railway logs --service web | grep ERROR

# Filter for Celery
railway logs --service web | grep -i celery
```

### Check Resource Usage

1. Go to **Web Service** → **Metrics**
2. Monitor:
   - **Memory usage**: Should stay under 1GB
   - **CPU usage**: Should average <50%
   - **Response times**: Target <500ms

### Check Execution Hours

1. Go to **Project** → **Settings** → **Usage**
2. Monitor execution hours
3. Hobby plan provides 500h, but allows overage

## Cost Monitoring

**Expected costs**:
- **Web service**: $5-8/month (720 hours)
- **PostgreSQL**: $0 (included)
- **Redis**: $0 (included)
- **Total**: $5-8/month

**Check current usage**:
1. Project → Settings → Usage
2. View current month's cost

## Updating Your App

### Push Updates

```bash
# Make changes locally
git add .
git commit -m "Update application"
git push origin main

# Railway auto-deploys
```

### Manual Migrations

If migrations don't run automatically:

```bash
railway run python myapp/manage.py migrate
```

### Restart Service

1. Go to **Web Service** → **Deployments**
2. Click **"..."** on latest deployment
3. Click **"Restart"**

## Environment Variables Reference

### Required

| Variable | Value | Purpose |
|----------|-------|---------|
| `ENVIRONMENT` | `production` | Sets production mode |
| `DJANGO_DEBUG` | `False` | Disables debug mode |
| `DJANGO_SECRET_KEY` | `<random-50-chars>` | Django security key |
| `DJANGO_ALLOWED_HOSTS` | `*.railway.app` | Allowed domains |

### Optional

| Variable | Default | Purpose |
|----------|---------|---------|
| `WEB_CONCURRENCY` | `1` | Gunicorn workers |
| `ENABLE_CELERY` | `false` | Enable background tasks |
| `ENABLE_CELERY_BEAT` | `false` | Enable scheduled tasks |
| `CELERY_WORKER_CONCURRENCY` | `1` | Celery worker processes |

### Auto-Provided by Railway

| Variable | Source | Purpose |
|----------|--------|---------|
| `DATABASE_URL` | PostgreSQL plugin | Database connection |
| `REDIS_URL` | Redis plugin | Cache/broker connection |
| `PORT` | Railway | HTTP port (usually 8000) |
| `RAILWAY_ENVIRONMENT` | Railway | Environment name |

## Custom Domain (Optional)

### Add Custom Domain

1. Go to **Web Service** → **Settings** → **Networking**
2. Click **"Custom Domain"**
3. Enter your domain (e.g., `mywebnovel.com`)
4. Follow DNS configuration instructions

### Update ALLOWED_HOSTS

```bash
DJANGO_ALLOWED_HOSTS=*.railway.app,mywebnovel.com,www.mywebnovel.com
```

## When to Upgrade to Pro

Upgrade to Pro Plan ($20/month) when:

- [ ] Traffic consistently exceeds 10-15 concurrent users
- [ ] You need separate services for better isolation
- [ ] You want advanced metrics and observability
- [ ] You're generating revenue
- [ ] Database queries are slow (need read replicas)

## Next Steps After Deployment

1. **Test all pages**: Homepage, book list, book detail, search
2. **Create test content**: Add books, chapters via admin
3. **Monitor logs**: Watch for errors
4. **Set up monitoring**: Use Railway metrics
5. **Plan upgrade**: When traffic grows, upgrade to Pro

## Getting Help

- **Railway Docs**: https://docs.railway.app
- **Railway Discord**: https://discord.gg/railway
- **Django Deployment**: https://docs.djangoproject.com/en/stable/howto/deployment/

## Summary

**What you deployed**:
- ✅ Django web application
- ✅ PostgreSQL database
- ✅ Redis cache
- ✅ Optional: Celery worker + beat

**Cost**: $5-8/month

**Time to deploy**: 15 minutes

**Next**: Test your site and add content!
