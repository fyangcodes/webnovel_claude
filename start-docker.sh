#!/bin/bash

# Color codes for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Webnovel Docker Environment Setup${NC}"
echo -e "${BLUE}========================================${NC}\n"

# Check if .env exists
if [ ! -f .env ]; then
    echo -e "${YELLOW}⚠️  No .env file found!${NC}"
    echo -e "Creating .env from .env.example..."
    cp .env.example .env
    echo -e "${GREEN}✓${NC} .env file created"
    echo -e "${YELLOW}⚠️  Please edit .env and add your OPENAI_API_KEY${NC}\n"
    exit 1
fi

# Build Docker images
echo -e "${BLUE}📦 Building Docker images...${NC}"
docker-compose build

# Start services
echo -e "\n${BLUE}🚀 Starting services...${NC}"
docker-compose up -d

# Wait for database to be ready
echo -e "\n${BLUE}⏳ Waiting for database to be ready...${NC}"
sleep 5

# Run migrations
echo -e "\n${BLUE}📊 Running database migrations...${NC}"
docker-compose exec -T web python myapp/manage.py migrate

# Load fixtures
echo -e "\n${BLUE}📦 Loading initial data...${NC}"
echo "from books.models import Language; print('exists' if Language.objects.exists() else 'none')" | docker-compose exec -T web python myapp/manage.py shell > /tmp/language_check.txt

if grep -q "none" /tmp/language_check.txt; then
    echo -e "${BLUE}Loading languages fixture...${NC}"
    docker-compose exec -T web python myapp/manage.py loaddata myapp/fixtures/languages.json
    echo -e "${GREEN}✓${NC} Loaded 5 languages (Chinese, English, German, French, Japanese)"
else
    echo -e "${GREEN}✓${NC} Languages already loaded"
fi

# Check if superuser exists
echo -e "\n${BLUE}👤 Checking for superuser...${NC}"
echo "from django.contrib.auth import get_user_model; User = get_user_model(); print('exists' if User.objects.filter(is_superuser=True).exists() else 'none')" | docker-compose exec -T web python myapp/manage.py shell > /tmp/superuser_check.txt

if grep -q "none" /tmp/superuser_check.txt; then
    echo -e "${BLUE}Loading admin user fixture...${NC}"
    docker-compose exec -T web python myapp/manage.py loaddata myapp/fixtures/users.json
    echo -e "${GREEN}✓${NC} Admin user created (username: admin, check fixtures/users.json for password)"
    echo -e "${YELLOW}⚠️  Or create your own with: ${GREEN}docker-compose exec web python myapp/manage.py createsuperuser${NC}"
else
    echo -e "${GREEN}✓${NC} Superuser already exists"
fi

# Backfill stats
echo -e "\n${BLUE}📈 Initializing stats models...${NC}"
docker-compose exec -T web python myapp/manage.py backfill_stats --dry-run

# Show status
echo -e "\n${BLUE}✅ Services Status:${NC}"
docker-compose ps

echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}  ✓ Docker environment is ready!${NC}"
echo -e "${GREEN}========================================${NC}"
echo -e "\n${BLUE}Access your application:${NC}"
echo -e "  • Django Web:      ${GREEN}http://localhost:8000${NC}"
echo -e "  • Django Admin:    ${GREEN}http://localhost:8000/admin${NC}"
echo -e "  • Celery Flower:   ${GREEN}http://localhost:5555${NC}"
echo -e "\n${BLUE}View logs:${NC}"
echo -e "  ${GREEN}docker-compose logs -f web${NC}"
echo -e "  ${GREEN}docker-compose logs -f celery_worker${NC}"
echo -e "\n${BLUE}Stop services:${NC}"
echo -e "  ${GREEN}docker-compose down${NC}"
echo -e "\n${BLUE}Full documentation:${NC} See ${GREEN}DOCKER_SETUP.md${NC}\n"
