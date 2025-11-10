# Docker Development Environment Setup

This guide will help you set up the complete development environment using Docker.

## 📋 Prerequisites

- Docker Desktop installed ([Download](https://www.docker.com/products/docker-desktop))
- Docker Compose (included with Docker Desktop)
- Git
- Text editor (VS Code recommended)

## 🚀 Quick Start

### 1. Clone and Setup Environment

```bash
# Clone the repository (if not already done)
git clone <your-repo-url>
cd webnovel_claude

# Copy environment file
cp .env.example .env

# Edit .env with your API keys (especially OPENAI_API_KEY)
nano .env  # or use your preferred editor
```

### 2. Build and Start All Services

```bash
# Build Docker images
docker-compose build

# Start all services (Django, PostgreSQL, Redis, Celery, Flower)
docker-compose up

# Or run in detached mode (background)
docker-compose up -d
```

### 3. Initialize Database

```bash
# Run migrations
docker-compose exec web python myapp/manage.py migrate

# Load initial data (languages and admin user)
docker-compose exec web python myapp/manage.py loaddata myapp/fixtures/languages.json
docker-compose exec web python myapp/manage.py loaddata myapp/fixtures/users.json

# OR create your own superuser instead of using fixtures
docker-compose exec web python myapp/manage.py createsuperuser

# (Optional) Initialize stats models for existing data
docker-compose exec web python myapp/manage.py backfill_stats
```

### 4. Access the Application

- **Django Web**: http://localhost:8000
- **Django Admin**: http://localhost:8000/admin
  - Default admin credentials (from fixtures):
    - Username: `admin`
    - Password: You'll need to reset it using: `docker-compose exec web python myapp/manage.py changepassword admin`
- **Celery Flower** (monitoring): http://localhost:5555
- **PostgreSQL**: localhost:5432 (user: postgres, password: postgres, db: webnovel)
- **Redis**: localhost:6379

**Note**: The fixtures include 5 languages (Chinese, English, German, French, Japanese) and an admin user. You can reset the admin password or create a new superuser with your own credentials.

## 🐳 Docker Services

Your `docker-compose.yml` includes these services:

| Service | Description | Port |
|---------|-------------|------|
| `db` | PostgreSQL 15 database | 5432 |
| `redis` | Redis cache & Celery broker | 6379 |
| `web` | Django application | 8000 |
| `celery_worker` | Background task processor | - |
| `celery_beat` | Task scheduler | - |
| `flower` | Celery monitoring UI | 5555 |

## 📝 Common Commands

### Service Management

```bash
# Start all services
docker-compose up

# Start specific service
docker-compose up web

# Stop all services
docker-compose down

# Stop and remove volumes (⚠️ deletes data!)
docker-compose down -v

# Restart a service
docker-compose restart web

# View logs
docker-compose logs -f web
docker-compose logs -f celery_worker
docker-compose logs -f celery_beat
```

### Django Commands

```bash
# Run Django commands
docker-compose exec web python myapp/manage.py <command>

# Examples:
docker-compose exec web python myapp/manage.py migrate
docker-compose exec web python myapp/manage.py createsuperuser
docker-compose exec web python myapp/manage.py changepassword admin
docker-compose exec web python myapp/manage.py collectstatic
docker-compose exec web python myapp/manage.py shell

# Load fixtures
docker-compose exec web python myapp/manage.py loaddata myapp/fixtures/languages.json
docker-compose exec web python myapp/manage.py loaddata myapp/fixtures/users.json

# Run management commands
docker-compose exec web python myapp/manage.py backfill_stats
docker-compose exec web python myapp/manage.py stats_report --language en --days 7
```

### Database Commands

```bash
# Access PostgreSQL shell
docker-compose exec db psql -U postgres -d webnovel

# Backup database
docker-compose exec db pg_dump -U postgres webnovel > backup.sql

# Restore database
docker-compose exec -T db psql -U postgres webnovel < backup.sql

# Reset database (⚠️ deletes all data!)
docker-compose down -v
docker-compose up -d db
docker-compose exec web python myapp/manage.py migrate
```

### Redis Commands

```bash
# Access Redis CLI
docker-compose exec redis redis-cli

# Common Redis commands:
# KEYS stats:*              # List all stats keys
# GET stats:chapter:1:views # Get chapter views
# FLUSHALL                  # Clear all Redis data (⚠️)
```

### Celery Commands

```bash
# View active tasks
docker-compose exec celery_worker celery -A myapp inspect active

# View scheduled tasks
docker-compose exec celery_beat celery -A myapp inspect scheduled

# Purge all tasks
docker-compose exec celery_worker celery -A myapp purge
```

## 🔧 Development Workflow

### Hot Reload

Docker is configured with volume mounts, so code changes are reflected immediately:

```yaml
volumes:
  - .:/app  # Your code is mounted into the container
```

Just edit files locally and refresh your browser!

### Installing New Python Packages

```bash
# Add package to requirements.txt
echo "new-package>=1.0.0" >> requirements.txt

# Rebuild the container
docker-compose build web

# Restart services
docker-compose up -d
```

### Running Tests

```bash
# Run all tests
docker-compose exec web python myapp/manage.py test

# Run specific app tests
docker-compose exec web python myapp/manage.py test books

# Run with coverage
docker-compose exec web coverage run myapp/manage.py test
docker-compose exec web coverage report
```

## 🐛 Troubleshooting

### Services Won't Start

```bash
# Check service status
docker-compose ps

# View logs for errors
docker-compose logs

# Restart all services
docker-compose restart
```

### Database Connection Errors

```bash
# Wait for database to be ready
docker-compose up db  # Wait for "database system is ready"

# Check database is running
docker-compose exec db pg_isready -U postgres
```

### Redis Connection Errors

```bash
# Check Redis is running
docker-compose exec redis redis-cli ping
# Should return: PONG
```

### Celery Tasks Not Running

```bash
# Check Celery worker logs
docker-compose logs celery_worker

# Check Celery beat logs
docker-compose logs celery_beat

# View Celery Flower dashboard
open http://localhost:5555
```

### Port Already in Use

```bash
# If port 8000 is taken, change in docker-compose.yml:
ports:
  - "8001:8000"  # Use 8001 on host instead

# Or stop the conflicting service
lsof -ti:8000 | xargs kill
```

### Reset Everything

```bash
# Nuclear option: delete everything and start fresh
docker-compose down -v
docker system prune -a
docker-compose build --no-cache
docker-compose up
```

## 📊 Monitoring

### Celery Flower Dashboard

Access at http://localhost:5555 to monitor:
- Active tasks
- Task history
- Worker status
- Task statistics

### Django Debug Toolbar (Optional)

Add to `requirements.txt`:
```
django-debug-toolbar>=4.2.0
```

Update `settings.py`:
```python
if DEBUG:
    INSTALLED_APPS += ['debug_toolbar']
    MIDDLEWARE += ['debug_toolbar.middleware.DebugToolbarMiddleware']
    INTERNAL_IPS = ['127.0.0.1', 'localhost']
```

## 🎯 Production Deployment

### Building for Production

```bash
# Build production image
docker build -t webnovel-app .

# Tag for registry
docker tag webnovel-app registry.railway.app/your-project

# Push to Railway (or your registry)
docker push registry.railway.app/your-project
```

### Environment Variables for Production

Set these in Railway or your hosting platform:

```bash
DJANGO_SECRET_KEY=<generate-strong-key>
DJANGO_DEBUG=False
DATABASE_URL=<provided-by-railway>
REDIS_URL=<provided-by-railway>
CELERY_BROKER_URL=<same-as-redis-url>
OPENAI_API_KEY=<your-key>
AWS_ACCESS_KEY_ID=<for-s3>
AWS_SECRET_ACCESS_KEY=<for-s3>
```

## 📚 Additional Resources

- [Docker Documentation](https://docs.docker.com/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [Django Docker Best Practices](https://docs.docker.com/samples/django/)
- [Celery Documentation](https://docs.celeryq.dev/)
- [Railway Documentation](https://docs.railway.app/)

## 🆘 Getting Help

If you encounter issues:

1. Check logs: `docker-compose logs -f`
2. Verify services are healthy: `docker-compose ps`
3. Check the troubleshooting section above
4. Review Docker Compose configuration in `docker-compose.yml`
5. Open an issue on GitHub

Happy coding! 🚀
